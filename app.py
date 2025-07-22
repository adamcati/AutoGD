from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import posthog
import stripe
import os
import uuid
import base64
from io import BytesIO
from config import config
from models import db, User
from forms import RegisterForm
from analytics import track_subscription_event, track_auth_event, track_session_event, track_feature_usage
from celery_app import make_celery

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Set SQLAlchemy configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = config[config_name].DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_timeout': 30,
        'pool_recycle': 1800,
    }

    # Initialize extensions
    db.init_app(app)
    
    # Create tables within application context
    with app.app_context():
        db.create_all()
    
    mail = Mail(app)
    login_manager = LoginManager(app)
    login_manager.login_view = 'login'
    
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    stripe.api_key = app.config['STRIPE_SECRET_KEY']
    
    # Initialize PostHog with both API key and host
    posthog.api_key = app.config['POSTHOG_API_KEY']
    posthog.host = app.config['POSTHOG_HOST'].strip()

    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )

    celery = make_celery(app)

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.filter_by(id=uuid.UUID(user_id)).first()
        except ValueError:
            return None

    def send_verification_email(email):
        try:
            token = serializer.dumps(email, salt='email-verification')
            verification_url = url_for('verify_email', token=token, _external=True)
            msg = Message(
                'Verify Your Email',
                sender=app.config['MAIL_USERNAME'],
                recipients=[email]
            )
            msg.body = f'Please verify your email by clicking the link below:\n\n{verification_url}'
            print(f"Attempting to send verification email to: {email}")
            mail.send(msg)
            print("Verification email sent successfully")
            return True
        except Exception as e:
            print(f"Error sending verification email: {str(e)}")
            return False

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        form = RegisterForm()
        if form.validate_on_submit():
            try:
                # Check if user already exists
                existing_user = User.query.filter_by(email=form.email.data).first()
                if existing_user:
                    flash('Email already registered. Please login instead.', 'error')
                    return redirect(url_for('login'))

                # Create new user
                user = User(
                    email=form.email.data,
                    password=generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=16)
                )
                db.session.add(user)
                db.session.commit()
                print(f"User created successfully with email: {user.email}")

                # Send verification email
                if send_verification_email(user.email):
                    track_auth_event(str(user.id), 'register', success=True)
                    flash('Registration successful. Please check your email to verify your account.', 'success')
                    return redirect(url_for('login'))
                else:
                    # If email sending fails, delete the user and show error
                    db.session.delete(user)
                    db.session.commit()
                    flash('Registration failed. Could not send verification email.', 'error')
                    return redirect(url_for('register'))

            except Exception as e:
                print(f"Registration error: {str(e)}")
                db.session.rollback()
                track_auth_event(None, 'register', success=False, error_message=str(e))
                flash(f'Registration failed: {str(e)}', 'error')
                return redirect(url_for('register'))
        return render_template('register.html', form=form)

    @app.route('/verify_email/<token>')
    def verify_email(token):
        try:
            email = serializer.loads(token, salt='email-verification', max_age=3600)
            user = User.query.filter_by(email=email).first()
            if user:
                user.is_verified = True
                db.session.commit()
                track_auth_event(str(user.id), 'verify_email', success=True)
                flash('Email verified successfully! You can now login.', 'success')
                return redirect(url_for('login'))
            else:
                flash('User not found. Please register again.', 'error')
                return redirect(url_for('register'))
        except Exception as e:
            print(f"Email verification error: {str(e)}")
            track_auth_event(None, 'verify_email', success=False, error_message=str(e))
            flash('Invalid or expired verification link. Please request a new one.', 'error')
            return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit("10 per minute")
    def login():
        if request.method == 'POST':
            email = request.form['email']
            raw_password = request.form['password']
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, raw_password):
                login_user(user)
                track_auth_event(str(user.id), 'login', success=True)
                track_session_event(str(user.id), 'start')
                return redirect(url_for('dashboard'))
            else:
                track_auth_event(None, 'login', success=False, error_message='Invalid credentials')
                flash('Invalid email or password', 'error')
        return render_template('login.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')

    @app.route('/logout')
    @login_required
    def logout():
        track_session_event(str(current_user.id), 'end')
        logout_user()
        return redirect(url_for('login'))

    @app.route('/checkout/<tier>')
    @login_required
    def create_checkout_session(tier):
        try:
            price_id = {
                'basic': os.getenv('STRIPE_BASIC_PRICE_ID'),
                'plus': os.getenv('STRIPE_PLUS_PRICE_ID'),
                'premium': os.getenv('STRIPE_PREMIUM_PRICE_ID')
            }.get(tier.lower())

            if not price_id:
                return jsonify({'error': 'Invalid subscription tier'}), 400

            checkout_session = stripe.checkout.Session.create(
                customer=current_user.stripe_customer_id,
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                success_url=url_for('success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=url_for('cancel', _external=True),
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/success')
    @login_required
    def success(tier):
        track_subscription_event(str(current_user.id), 'subscription_success')
        return render_template('success.html')

    @app.route('/cancel')
    @login_required
    def cancel():
        track_subscription_event(str(current_user.id), 'subscription_cancel')
        return render_template('cancel.html')

    @app.route('/health')
    def health_check():
        try:
            # Check database connection
            db.session.execute('SELECT 1')
            return jsonify({'status': 'healthy', 'database': 'connected'}), 200
        except Exception as e:
            return jsonify({'status': 'unhealthy', 'database': str(e)}), 500

    @app.route('/process_roi', methods=['POST'])
    @limiter.limit("10 per minute")
    def process_roi():
        from tasks import ocr_task
        try:
          data = request.json
          x, y, w, h = data['x'], data['y'], data['w'], data['h']
          image_data = data['image_data']  # This is a data URL (e.g., 'data:image/png;base64,...')
          # Remove the header of the data URL
          header, encoded = image_data.split(',', 1)
          if len(encoded) > 2 * 1024 * 1024:  # 2MB limit
              return jsonify({'error': 'ROI image too large'}), 400
          img_bytes = base64.b64decode(encoded)
          # img = Image.open(BytesIO(img_bytes)) THIS WILL BE IN THE OCR FUNCTION
          # Now you have the cropped ROI as a PIL Image object
          # Run your OCR here...
          task = ocr_task.apply_async(args=[img_bytes])
          return jsonify({'task_id': task.id}), 202
        except Exception as e:
            app.logger.error(f"Error processing ROI: {str(e)}")
            return jsonify({'error': 'Server error'}), 500
        
    @app.route('/get_ocr_result/<task_id>')
    def get_ocr_result(task_id):
        from tasks import ocr_task
        task = ocr_task.AsyncResult(task_id)
        if task.state == 'PENDING':
            return jsonify({'state': 'PENDING', 'result': None})
        elif task.state == 'SUCCESS':
            return jsonify({'state': 'SUCCESS', 'result': task.result})
        else:
            return jsonify({'state': task.state, 'result': None})

    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run()





