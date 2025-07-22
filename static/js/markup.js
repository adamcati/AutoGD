// markup.js
let canvas = document.getElementById('markup-canvas');
let ctx = canvas.getContext('2d');
let image = null;
let scale = 1, minScale = 0.2, maxScale = 5, offsetX = 0, offsetY = 0;
let isPanning = false, startPan = {x:0, y:0};
let isDrawing = false, drawStart = null;
let rectangles = [], selectedRect = null;

// Helper to draw a red X at (sx, sy)
function drawDeleteX(sx, sy, highlight=false) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(sx, sy, 10, 0, 2*Math.PI);
    ctx.fillStyle = highlight ? '#f8d7da' : 'rgba(255,255,255,0.8)';
    ctx.fill();
    ctx.strokeStyle = highlight ? '#dc3545' : '#ccc';
    ctx.lineWidth = 1;
    ctx.stroke();
    // Draw X
    ctx.strokeStyle = '#dc3545';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(sx-5, sy-5); ctx.lineTo(sx+5, sy+5);
    ctx.moveTo(sx+5, sy-5); ctx.lineTo(sx-5, sy+5);
    ctx.stroke();
    ctx.restore();
}

let trashIconRects = [];

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    trashIconRects = [];
    if (image) {
        ctx.save();
        ctx.setTransform(scale, 0, 0, scale, offsetX, offsetY);
        ctx.drawImage(image, 0, 0);
        ctx.restore();
        // Draw rectangles and delete Xs
        rectangles.forEach((rect, i) => {
            ctx.save();
            ctx.setTransform(scale, 0, 0, scale, offsetX, offsetY);
            ctx.strokeStyle = (i === selectedRect) ? 'red' : 'blue';
            ctx.lineWidth = 2/scale;
            ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
            ctx.restore();
            // Draw delete X in screen coordinates
            let topRight = worldToScreen(rect.x+rect.w, rect.y);
            let highlight = (i === trashIconHoverIndex);
            drawDeleteX(topRight.x, topRight.y, highlight);
            trashIconRects.push({i, x: topRight.x, y: topRight.y, r: 12});
        });
    }
}

function screenToWorld(x, y) {
    return {
        x: (x - offsetX) / scale,
        y: (y - offsetY) / scale
    };
}
function worldToScreen(x, y) {
    return {
        x: x * scale + offsetX,
        y: y * scale + offsetY
    };
}

let trashIconHoverIndex = null;

canvas.addEventListener('mousemove', (e) => {
    if (!image) return;
    // Trash icon hover detection
    trashIconHoverIndex = null;
    trashIconRects.forEach(({i, x, y, r}) => {
        let dx = e.offsetX - x, dy = e.offsetY - y;
        if (dx*dx + dy*dy < r*r) trashIconHoverIndex = i;
    });
    if (isPanning) {
        offsetX += e.offsetX - startPan.x;
        offsetY += e.offsetY - startPan.y;
        startPan = {x: e.offsetX, y: e.offsetY};
        draw();
    } else if (isDrawing) {
        let {x, y} = screenToWorld(e.offsetX, e.offsetY);
        let w = x - drawStart.x, h = y - drawStart.y;
        draw();
        ctx.save();
        ctx.setTransform(scale, 0, 0, scale, offsetX, offsetY);
        ctx.strokeStyle = 'green';
        ctx.lineWidth = 2/scale;
        ctx.strokeRect(drawStart.x, drawStart.y, w, h);
        ctx.restore();
    } else {
        draw();
    }
});

canvas.addEventListener('mousedown', (e) => {
    if (!image) return;
    // Trash icon click
    if (trashIconHoverIndex !== null) {
        rectangles.splice(trashIconHoverIndex, 1);
        selectedRect = null;
        draw();
        return;
    }
    if (e.ctrlKey) {
        isPanning = true;
        startPan = {x: e.offsetX, y: e.offsetY};
    } else {
        let {x, y} = screenToWorld(e.offsetX, e.offsetY);
        // Check if clicking inside a rectangle
        selectedRect = null;
        rectangles.forEach((rect, i) => {
            if (x >= rect.x && x <= rect.x+rect.w && y >= rect.y && y <= rect.y+rect.h) {
                selectedRect = i;
            }
        });
        if (selectedRect === null) {
            isDrawing = true;
            drawStart = {x, y};
        }
        draw();
    }
});
canvas.addEventListener('mouseup', (e) => {
    if (!image) return;
    if (isPanning) {
        isPanning = false;
    } else if (isDrawing) {
        let {x, y} = screenToWorld(e.offsetX, e.offsetY);
        let w = x - drawStart.x, h = y - drawStart.y;
        if (Math.abs(w) > 10 && Math.abs(h) > 10) {
            let newRect = {x: drawStart.x, y: drawStart.y, w, h};
            rectangles.push(newRect);
            sendROIToServer(newRect);
        }
        isDrawing = false;
        draw();
    }
});
canvas.addEventListener('wheel', (e) => {
    if (!image || !e.ctrlKey) return;
    e.preventDefault();
    let mouse = screenToWorld(e.offsetX, e.offsetY);
    let oldScale = scale;
    scale *= (e.deltaY < 0) ? 1.1 : 0.9;
    scale = Math.max(minScale, Math.min(maxScale, scale));
    // Adjust offset so zoom is centered on mouse
    offsetX -= (mouse.x * scale - mouse.x * oldScale);
    offsetY -= (mouse.y * scale - mouse.y * oldScale);
    draw();
}, {passive:false});

canvas.addEventListener('mouseleave', () => { isPanning = false; isDrawing = false; });

document.getElementById('image-upload-form').addEventListener('submit', function(e) {
    e.preventDefault();
    let file = document.getElementById('image-input').files[0];
    if (!file) return;
    let reader = new FileReader();
    reader.onload = function(ev) {
        image = new window.Image();
        image.onload = function() {
            scale = Math.min(canvas.width/image.width, canvas.height/image.height);
            offsetX = (canvas.width - image.width*scale)/2;
            offsetY = (canvas.height - image.height*scale)/2;
            rectangles = [];
            selectedRect = null;
            draw();
            document.getElementById('canvas-section').style.display = '';
        };
        image.src = ev.target.result;
    };
    reader.readAsDataURL(file);
});

document.getElementById('delete-rect-btn').addEventListener('click', function() {
    if (selectedRect !== null) {
        rectangles.splice(selectedRect, 1);
        selectedRect = null;
        draw();
    }
});
document.getElementById('reset-btn').addEventListener('click', function() {
    rectangles = [];
    selectedRect = null;
    draw();
});

// Redraw on window resize
window.addEventListener('resize', draw);

function sendROIToServer(rect) {
    const roiImageData = getROICroppedImageData(rect);
    fetch('/process_roi', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            x: rect.x, y: rect.y, w: rect.w, h: rect.h,
            image_data: roiImageData // base64 PNG
        })
    })
    .then(res => res.json())
    .then(data => {
        // Update the UI with OCR result, etc.
        console.log('OCR result:', data.text);
        // You can display this result near the rectangle
    });
}

function getROICroppedImageData(rect) {
    // Create an offscreen canvas to crop the ROI
    let cropCanvas = document.createElement('canvas');
    cropCanvas.width = Math.abs(rect.w);
    cropCanvas.height = Math.abs(rect.h);
    let cropCtx = cropCanvas.getContext('2d');
    // Draw the ROI from the main image
    cropCtx.drawImage(
        image,
        rect.x, rect.y, rect.w, rect.h, // source
        0, 0, Math.abs(rect.w), Math.abs(rect.h) // destination
    );
    // Get the base64-encoded image data (PNG)
    return cropCanvas.toDataURL('image/png');
} 