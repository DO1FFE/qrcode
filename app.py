import os
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    flash,
)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
    UserMixin,
)
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
import qrcode.image.svg
from PIL import ImageColor
import stripe



app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
# Use a database file inside the application directory. This avoids absolute
# paths that may not exist when the application is started via systemd or in
# other environments.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(
    app.root_path, 'database.db'
)
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'qrcodes')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed number of QR codes per plan
PLAN_LIMITS = {
    'basic': 1,
    'starter': 5,
    'pro': 20,
    'premium': 50,
    'unlimited': None,
}

# Monthly prices in Euro cents for Stripe
STRIPE_PRICES = {
    'starter': 99,
    'pro': 199,
    'premium': 499,
    'unlimited': 999,
}

# Yearly prices with 30% discount applied
STRIPE_PRICES_YEARLY = {
    'starter': 832,
    'pro': 1672,
    'premium': 4192,
    'unlimited': 8392,
}

# Provide current year to templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

# Expose plan limits to templates
@app.context_processor
def inject_plan_limits():
    return {'PLAN_LIMITS': PLAN_LIMITS}

# Database

db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    plan = db.Column(db.String(20), default='basic')
    upgrade_method = db.Column(db.String(20))
    paypal_subscription_id = db.Column(db.String(255))
    plan_expires_at = db.Column(db.DateTime(timezone=True))
    plan_cancelled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    qrcodes = db.relationship('QRCode', backref='user', lazy=True)

class QRCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048))
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    png_path = db.Column(db.String(255))
    svg_path = db.Column(db.String(255))
    jpg_path = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    @property
    def created_at_local(self):
        return self.created_at.astimezone(ZoneInfo("Europe/Berlin"))


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Integer)
    period = db.Column(db.String(10))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

# Login manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.before_request
def check_plan_expiration():
    if current_user.is_authenticated and current_user.plan != 'basic':
        if (
            current_user.plan_cancelled
            and current_user.plan_expires_at
            and current_user.plan_expires_at <= datetime.utcnow()
        ):
            current_user.plan = 'basic'
            current_user.plan_cancelled = False
            current_user.paypal_subscription_id = None
            db.session.commit()


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Benutzername bereits vergeben')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email bereits vergeben')
            return redirect(url_for('register'))
        user = User(
            username=username,
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
        )
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
        if (
            user
            and user.password_hash
            and check_password_hash(user.password_hash, password)
        ):
            login_user(user)
            return redirect(url_for('index'))
        flash('Ungültige Anmeldedaten')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        current_user.name = request.form.get('name')
        current_user.email = request.form.get('email')
        password = request.form.get('password')
        if password:
            current_user.password_hash = generate_password_hash(password)
        db.session.commit()
        flash('Profil aktualisiert')
        return redirect(url_for('profile'))
    remaining = None
    next_charge = None
    if current_user.plan_expires_at:
        remaining = current_user.plan_expires_at - datetime.utcnow()
        next_charge = current_user.plan_expires_at.astimezone(
            ZoneInfo("Europe/Berlin")
        )
    return render_template(
        'profile.html',
        remaining=remaining,
        next_charge=next_charge,
    )


@app.route('/upgrade', methods=['GET', 'POST'])
@login_required
def upgrade():
    if request.method == 'POST':
        allow_new_plan = current_user.plan == 'basic' or (
            current_user.plan_expires_at
            and current_user.plan_expires_at <= datetime.utcnow()
        )
        if not allow_new_plan:
            flash('Planwechsel erst nach Ablauf des aktuellen Plans möglich.')
            return redirect(url_for('upgrade'))
        code = request.form.get('code', '').strip()
        if code == '2025STARTER':
            current_user.plan = 'starter'
            current_user.upgrade_method = f'code:{code}'
            current_user.plan_expires_at = datetime.utcnow() + timedelta(days=30)
            current_user.plan_cancelled = False
            db.session.add(Payment(user_id=current_user.id, amount=0, period='code'))
            db.session.commit()
            enforce_qrcode_limit(current_user)
            flash('Starter Plan aktiviert!')
        elif code == '2025PRO':
            current_user.plan = 'pro'
            current_user.upgrade_method = f'code:{code}'
            current_user.plan_expires_at = datetime.utcnow() + timedelta(days=30)
            current_user.plan_cancelled = False
            db.session.add(Payment(user_id=current_user.id, amount=0, period='code'))
            db.session.commit()
            enforce_qrcode_limit(current_user)
            flash('Pro Plan aktiviert!')
        elif code == '2025PREMIUM':
            current_user.plan = 'premium'
            current_user.upgrade_method = f'code:{code}'
            current_user.plan_expires_at = datetime.utcnow() + timedelta(days=30)
            current_user.plan_cancelled = False
            db.session.add(Payment(user_id=current_user.id, amount=0, period='code'))
            db.session.commit()
            enforce_qrcode_limit(current_user)
            flash('Premium Plan aktiviert!')
        elif code == '2025UNLIMITED':
            current_user.plan = 'unlimited'
            current_user.upgrade_method = f'code:{code}'
            current_user.plan_expires_at = datetime.utcnow() + timedelta(days=30)
            current_user.plan_cancelled = False
            db.session.add(Payment(user_id=current_user.id, amount=0, period='code'))
            db.session.commit()
            enforce_qrcode_limit(current_user)
            flash('Unlimited Plan aktiviert!')
        else:
            flash('Ungültiger Code')
    allow_new_plan = current_user.plan == 'basic' or (
        current_user.plan_expires_at
        and current_user.plan_expires_at <= datetime.utcnow()
    )
    next_charge = None
    if current_user.plan_expires_at:
        next_charge = current_user.plan_expires_at.astimezone(
            ZoneInfo("Europe/Berlin")
        )
    return render_template(
        'upgrade.html',
        allow_new_plan=allow_new_plan,
        next_charge=next_charge,
    )


@app.route('/cancel_subscription')
@login_required
def cancel_subscription():
    if current_user.paypal_subscription_id:
        cancel_paypal_subscription(current_user.paypal_subscription_id)
    current_user.plan_cancelled = True
    current_user.upgrade_method = 'cancelled'
    db.session.commit()
    flash('Abo gekündigt. Dein Plan bleibt bis zum Ablauf der aktuellen Laufzeit aktiv. Keine Rückerstattung.')
    return redirect(url_for('profile'))


@app.route('/create_checkout_session/<plan>', methods=['POST'])
@login_required
def create_checkout_session(plan):
    period = request.args.get('period', 'month')
    prices = STRIPE_PRICES if period == 'month' else STRIPE_PRICES_YEARLY
    interval = 'month' if period == 'month' else 'year'
    if plan not in prices:
        return 'Invalid plan', 400
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f'{plan.capitalize()} Plan'},
                    'unit_amount': prices[plan],
                    'recurring': {'interval': interval},
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('stripe_success', plan=plan, _external=True) + f'?period={period}',
            cancel_url=url_for('upgrade', _external=True),
            customer_email=current_user.email,
        )
        return redirect(session.url)
    except Exception as e:
        print('Stripe error:', e)
        flash('Fehler bei Stripe.')
        return redirect(url_for('upgrade'))


@app.route('/stripe_success/<plan>')
@login_required
def stripe_success(plan):
    if plan not in PLAN_LIMITS:
        return 'Invalid plan', 400
    period = request.args.get('period', 'month')
    current_user.plan = plan
    current_user.upgrade_method = 'stripe'
    if period == 'year':
        current_user.plan_expires_at = datetime.utcnow() + timedelta(days=365)
    else:
        current_user.plan_expires_at = datetime.utcnow() + timedelta(days=30)
    current_user.plan_cancelled = False
    prices = STRIPE_PRICES if period == 'month' else STRIPE_PRICES_YEARLY
    amount = prices.get(plan, 0)
    payment = Payment(user_id=current_user.id, amount=amount, period=period)
    db.session.add(payment)
    db.session.commit()
    enforce_qrcode_limit(current_user)
    flash(f'{plan.capitalize()} Plan aktiviert!')
    return redirect(url_for('profile'))

# Helper to generate qr code files

def generate_qr_files(
    url,
    color='black',
    bgcolor='white',
    rounded=False,
    user_id=None,
):
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=1,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Adjust box size so the final image fits within 400px.
    max_pixels = 400
    qr.box_size = max(1, max_pixels // qr.modules_count)

    drawer = RoundedModuleDrawer() if rounded else None
    front = ImageColor.getcolor(color, "RGB")
    back = ImageColor.getcolor(bgcolor, "RGB")
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=drawer,
        color_mask=SolidFillColorMask(front_color=front, back_color=back),
    )
    qr_id = os.urandom(8).hex()
    user_folder = (
        os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
        if user_id
        else app.config['UPLOAD_FOLDER']
    )
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


def enforce_qrcode_limit(user):
    limit = PLAN_LIMITS.get(user.plan)
    if limit is None:
        return
    qrs = QRCode.query.filter_by(user_id=user.id).order_by(QRCode.id).all()
    excess = len(qrs) - limit
    if excess > 0:
        for qr in qrs[:excess]:
            for path in [qr.png_path, qr.jpg_path, qr.svg_path]:
                if path and os.path.exists(path):
                    os.remove(path)
            db.session.delete(qr)
        db.session.commit()


def cancel_paypal_subscription(sub_id):
    client_id = os.environ.get('PAYPAL_CLIENT_ID')
    client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')
    base_url = os.environ.get('PAYPAL_BASE_URL', 'https://api-m.paypal.com')
    if not (client_id and client_secret):
        return
    try:
        auth = requests.post(
            f"{base_url}/v1/oauth2/token",
            headers={"Accept": "application/json"},
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
        )
        auth.raise_for_status()
        token = auth.json().get("access_token")
        requests.post(
            f"{base_url}/v1/billing/subscriptions/{sub_id}/cancel",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"reason": "User cancellation"},
        )
    except Exception as e:
        print("Failed to cancel PayPal subscription:", e)

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
        color = request.form.get('color', 'black')
        bgcolor = request.form.get('bgcolor', 'white')
        rounded = request.form.get('rounded') == 'on'
        description = request.form.get('description')
        qr_id, png_path, jpg_path, svg_path = generate_qr_files(
            url_input,
            color=color,
            bgcolor=bgcolor,
            rounded=rounded,
            user_id=current_user.id,
        )
        qr = QRCode(
            url=url_input,
            description=description,
            png_path=png_path,
            jpg_path=jpg_path,
            svg_path=svg_path,
            user=current_user,
        )
        db.session.add(qr)
        db.session.commit()
        flash('QR-Code erstellt!')
        return redirect(url_for('index'))

    qrs = (
        QRCode.query.filter_by(user_id=current_user.id).all()
        if current_user.is_authenticated
        else []
    )
    limit = (
        PLAN_LIMITS.get(current_user.plan)
        if current_user.is_authenticated
        else None
    )
    remaining = None
    if current_user.is_authenticated and limit is not None:
        remaining = max(0, limit - len(qrs))
    limit_reached = remaining == 0 if remaining is not None else False
    return render_template(
        'index.html',
        qrcodes=qrs,
        limit_reached=limit_reached,
        remaining=remaining,
        limit=limit,
    )

@app.route('/preview/<int:qr_id>')
def preview(qr_id):
    qr = QRCode.query.get_or_404(qr_id)
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
    return current_user.is_authenticated and current_user.username == 'DO1FFE'


@app.route('/admin')
@login_required
def admin_panel():
    if not is_admin():
        return 'Unauthorized', 403
    users = User.query.all()
    total_qrcodes = QRCode.query.count()
    return render_template('admin.html', users=users, total_qrcodes=total_qrcodes)


@app.route('/admin/stats')
@login_required
def admin_stats():
    if not is_admin():
        return 'Unauthorized', 403
    return render_template('admin_stats.html')


@app.route('/admin/stats/data')
@login_required
def admin_stats_data():
    if not is_admin():
        return 'Unauthorized', 403
    now = datetime.utcnow()
    one_day = now - timedelta(days=1)
    day_labels = []
    user_counts = []
    qr_counts = []
    for i in range(24):
        hour = (one_day + timedelta(hours=i+1)).replace(minute=0, second=0, microsecond=0)
        label = hour.strftime('%H')
        day_labels.append(label)
        uc = db.session.query(func.count(User.id)).filter(User.created_at >= hour - timedelta(hours=1), User.created_at < hour).scalar()
        qc = db.session.query(func.count(QRCode.id)).filter(QRCode.created_at >= hour - timedelta(hours=1), QRCode.created_at < hour).scalar()
        user_counts.append(uc or 0)
        qr_counts.append(qc or 0)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_revenue = db.session.query(func.sum(Payment.amount)).filter(Payment.created_at >= month_start).scalar() or 0
    monthly_subs = db.session.query(func.count(Payment.id)).filter(Payment.period == 'month').scalar() or 0
    yearly_subs = db.session.query(func.count(Payment.id)).filter(Payment.period == 'year').scalar() or 0

    return {
        'hours': day_labels,
        'user_counts': user_counts,
        'qr_counts': qr_counts,
        'monthly_subs': monthly_subs,
        'yearly_subs': yearly_subs,
        'month_revenue': month_revenue / 100.0,
    }


@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not is_admin():
        return 'Unauthorized', 403
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')

        if user.username != new_username and User.query.filter_by(username=new_username).first():
            flash('Benutzername bereits vergeben')
            return redirect(url_for('edit_user', user_id=user.id))

        if user.email != new_email and User.query.filter_by(email=new_email).first():
            flash('Email bereits vergeben')
            return redirect(url_for('edit_user', user_id=user.id))

        user.username = new_username
        user.name = request.form.get('name')
        user.email = new_email
        user.plan = request.form.get('plan')
        user.upgrade_method = request.form.get('upgrade_method')

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('Fehler beim Speichern der Änderungen')
            return redirect(url_for('edit_user', user_id=user.id))

        enforce_qrcode_limit(user)
        flash('Benutzer aktualisiert')
        return redirect(url_for('admin_panel'))
    return render_template('edit_user.html', user=user)


@app.route('/admin/user/<int:user_id>/qrcodes')
@login_required
def admin_user_qrcodes(user_id):
    if not is_admin():
        return 'Unauthorized', 403
    user = User.query.get_or_404(user_id)
    qrcodes = QRCode.query.filter_by(user_id=user_id).all()
    return render_template('user_qrcodes.html', user=user, qrcodes=qrcodes)


@app.route('/admin/qrcode/<int:qr_id>/delete', methods=['POST'])
@login_required
def admin_delete_qrcode(qr_id):
    if not is_admin():
        return 'Unauthorized', 403
    qr = QRCode.query.get_or_404(qr_id)
    user_id = qr.user_id
    for path in [qr.png_path, qr.jpg_path, qr.svg_path]:
        if path and os.path.exists(path):
            os.remove(path)
    db.session.delete(qr)
    db.session.commit()
    flash('QR-Code gelöscht')
    return redirect(url_for('admin_user_qrcodes', user_id=user_id))


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


@app.route('/impressum')
def impressum():
    return render_template('impressum.html')


@app.route('/datenschutz')
def privacy():
    return render_template('datenschutz.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Ensure older databases contain the new column introduced for
        # tracking how a user upgraded. SQLite will ignore the command if the
        # column already exists.
        with db.engine.begin() as conn:
            result = conn.execute(text('PRAGMA table_info(user)'))
            columns = [row[1] for row in result]
            if 'upgrade_method' not in columns:
                conn.execute(
                    text(
                        'ALTER TABLE user ADD COLUMN upgrade_method '
                        'VARCHAR(20)'
                    )
                )
            if 'paypal_subscription_id' not in columns:
                conn.execute(
                    text(
                        'ALTER TABLE user ADD COLUMN paypal_subscription_id '
                        'VARCHAR(255)'
                    )
                )
            if 'plan_expires_at' not in columns:
                conn.execute(
                    text(
                        'ALTER TABLE user ADD COLUMN plan_expires_at DATETIME'
                    )
                )
            if 'plan_cancelled' not in columns:
                conn.execute(
                    text(
                        'ALTER TABLE user ADD COLUMN plan_cancelled BOOLEAN '
                        'DEFAULT 0'
                    )
                )
            if 'created_at' not in columns:
                conn.execute(
                    text(
                        'ALTER TABLE user ADD COLUMN created_at DATETIME'
                    )
                )
                conn.execute(text("UPDATE user SET created_at = CURRENT_TIMESTAMP"))
            result = conn.execute(text('PRAGMA table_info(qr_code)'))
            qr_columns = [row[1] for row in result]
            if 'created_at' not in qr_columns:
                conn.execute(text('ALTER TABLE qr_code ADD COLUMN created_at DATETIME'))
                conn.execute(text("UPDATE qr_code SET created_at = CURRENT_TIMESTAMP"))
            result = conn.execute(text('PRAGMA table_info(payment)'))
            payment_columns = [row[1] for row in result]
            if not payment_columns:
                Payment.__table__.create(conn)
    debug_mode = os.environ.get('FLASK_DEBUG') == '1'
    app.run(host='0.0.0.0', port=8010, debug=debug_mode)
