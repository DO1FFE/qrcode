import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_dance.contrib.google import make_google_blueprint, google
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
import qrcode.image.svg
from PIL import ImageColor

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'qrcodes')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed number of QR codes per plan
PLAN_LIMITS = {
    'basic': 1,
    'starter': 5,
    'pro': 20,
    'premium': 50,
    'unlimited': None,
}

# Provide current year to templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

# Database

db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True)
    username = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    plan = db.Column(db.String(20), default='basic')
    upgrade_method = db.Column(db.String(20))
    qrcodes = db.relationship('QRCode', backref='user', lazy=True)

class QRCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048))
    description = db.Column(db.String(255))
    png_path = db.Column(db.String(255))
    svg_path = db.Column(db.String(255))
    jpg_path = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# Login manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Google OAuth using Flask-Dance
os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')
google_bp = make_google_blueprint(scope=['profile', 'email'])
app.register_blueprint(google_bp, url_prefix='/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Benutzername bereits vergeben')
            return redirect(url_for('register'))
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Ungültige Anmeldedaten')
    return render_template('login.html')

@app.route('/login/google')
def login_google():
    if not google.authorized:
        return redirect(url_for('google.login'))
    resp = google.get('/oauth2/v2/userinfo')
    assert resp.ok, resp.text
    info = resp.json()
    user = User.query.filter_by(google_id=info['id']).first()
    if not user:
        user = User(google_id=info['id'], name=info.get('name'), email=info.get('email'))
        db.session.add(user)
        db.session.commit()
    login_user(user)
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/upgrade', methods=['GET', 'POST'])
@login_required
def upgrade():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if code == '2025STARTER':
            current_user.plan = 'starter'
            current_user.upgrade_method = f'code:{code}'
            db.session.commit()
            flash('Starter Plan aktiviert!')
        elif code == '2025PRO':
            current_user.plan = 'pro'
            current_user.upgrade_method = f'code:{code}'
            db.session.commit()
            flash('Pro Plan aktiviert!')
        elif code == '2025PREMIUM':
            current_user.plan = 'premium'
            current_user.upgrade_method = f'code:{code}'
            db.session.commit()
            flash('Premium Plan aktiviert!')
        elif code == '2025UNLIMITED':
            current_user.plan = 'unlimited'
            current_user.upgrade_method = f'code:{code}'
            db.session.commit()
            flash('Unlimited Plan aktiviert!')
        else:
            flash('Ungültiger Code')
    return render_template('upgrade.html')

# Helper to generate qr code files

def generate_qr_files(url, size=10, color='black', bgcolor='white', rounded=False, user_id=None):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=size, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    drawer = RoundedModuleDrawer() if rounded else None
    front = ImageColor.getcolor(color, "RGBA")
    back = ImageColor.getcolor(bgcolor, "RGBA")
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=drawer,
        color_mask=SolidFillColorMask(front_color=front, back_color=back),
    )
    qr_id = os.urandom(8).hex()
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id)) if user_id else app.config['UPLOAD_FOLDER']
    os.makedirs(user_folder, exist_ok=True)

    png_path = os.path.join(user_folder, f'{qr_id}.png')
    img.save(png_path)

    jpg_path = os.path.join(user_folder, f'{qr_id}.jpg')
    img.convert('RGB').save(jpg_path)

    svg_img = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
    svg_path = os.path.join(user_folder, f'{qr_id}.svg')
    with open(svg_path, 'wb') as f:
        svg_img.save(f)

    return qr_id, png_path, jpg_path, svg_path

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Bitte einloggen um QR-Codes zu speichern.')
            return redirect(url_for('index'))
        limit = PLAN_LIMITS.get(current_user.plan)
        if limit is not None and len(current_user.qrcodes) >= limit:
            flash('Limit für deinen Plan erreicht.')
            return redirect(url_for('index'))
        url_input = request.form.get('url')
        size = int(request.form.get('size', 10))
        color = request.form.get('color', 'black')
        bgcolor = request.form.get('bgcolor', 'white')
        rounded = request.form.get('rounded') == 'on'
        description = request.form.get('description')
        qr_id, png_path, jpg_path, svg_path = generate_qr_files(url_input, size=size, color=color, bgcolor=bgcolor, rounded=rounded, user_id=current_user.id)
        qr = QRCode(url=url_input, description=description, png_path=png_path, jpg_path=jpg_path, svg_path=svg_path, user=current_user)
        db.session.add(qr)
        db.session.commit()
        flash('QR-Code erstellt!')
        return redirect(url_for('index'))

    qrs = QRCode.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    limit = PLAN_LIMITS.get(current_user.plan) if current_user.is_authenticated else None
    limit_reached = limit is not None and len(qrs) >= limit
    return render_template('index.html', qrcodes=qrs, limit_reached=limit_reached)

@app.route('/preview/<int:qr_id>')
@login_required
def preview(qr_id):
    qr = QRCode.query.get_or_404(qr_id)
    if qr.user_id != current_user.id:
        return 'Unauthorized', 403
    directory = os.path.dirname(qr.png_path)
    filename = os.path.basename(qr.png_path)
    return send_from_directory(directory, filename)

@app.route('/download/<int:qr_id>/<fmt>')
@login_required
def download(qr_id, fmt):
    qr = QRCode.query.get_or_404(qr_id)
    if qr.user_id != current_user.id:
        return 'Unauthorized', 403
    if fmt == 'png':
        path = qr.png_path
    elif fmt == 'jpg':
        path = qr.jpg_path
    elif fmt == 'svg':
        path = qr.svg_path
    else:
        return 'Unsupported format', 400
    directory = os.path.dirname(path)
    filename = os.path.basename(path)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/delete/<int:qr_id>', methods=['POST'])
@login_required
def delete(qr_id):
    qr = QRCode.query.get_or_404(qr_id)
    if qr.user_id != current_user.id:
        return 'Unauthorized', 403
    for path in [qr.png_path, qr.jpg_path, qr.svg_path]:
        if path and os.path.exists(path):
            os.remove(path)
    db.session.delete(qr)
    db.session.commit()
    flash('QR-Code gelöscht')
    return redirect(url_for('index'))


def is_admin():
    return current_user.is_authenticated and (current_user.username == 'DO1FFE')


@app.route('/admin')
@login_required
def admin_panel():
    if not is_admin():
        return 'Unauthorized', 403
    users = User.query.all()
    return render_template('admin.html', users=users)


@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not is_admin():
        return 'Unauthorized', 403
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        user.plan = request.form.get('plan')
        user.upgrade_method = request.form.get('upgrade_method')
        db.session.commit()
        flash('Benutzer aktualisiert')
        return redirect(url_for('admin_panel'))
    return render_template('edit_user.html', user=user)


@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not is_admin():
        return 'Unauthorized', 403
    user = User.query.get_or_404(user_id)
    # remove QR code files
    for qr in user.qrcodes:
        for path in [qr.png_path, qr.jpg_path, qr.svg_path]:
            if path and os.path.exists(path):
                os.remove(path)
        db.session.delete(qr)
    db.session.delete(user)
    db.session.commit()
    flash('Benutzer gelöscht')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    debug_mode = os.environ.get('FLASK_DEBUG') == '1'
    app.run(host='0.0.0.0', port=8010, debug=debug_mode)
