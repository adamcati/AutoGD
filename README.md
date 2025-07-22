# AutoGD
>Note: The ML model for automatic labeling and data extraction using OCR from GD&T drawings is currently in development as I want state-of-the-art OCR and labeling, thus I'm creating and training a custom model!

#Getting started

1.Clone the repository

  git clone https://github.com/adamcati/AutoGD.git
  cd AutoGD

2. Install Dependencies

  pip install -r requirements.txt

3. Configure Enivronment Variables
Copy .env.example to .env and fill in your credentials:

  cp .env.example .env

4. Run the Application
   python app.py

Project Structure:
app.py – Main Flask application and routes
models.py – Database models (User, etc.)
forms.py – WTForms for user input
analytics.py – Analytics and event tracking
config.py – Configuration and environment variable loading
templates/ – HTML templates (dashboard, login, register, etc.)
static/ – Static assets (CSS, JS, images)

License
This project is licensed under the MIT License

Acknowledgements
Flask
Stripe
PostHog
Supabase

Questions or feedback?
Open an issue or contact me via GitHub!
