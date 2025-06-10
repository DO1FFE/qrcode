# qrcode
Ein einfacher QR-Code Generator als Flask-Webanwendung.
Die Anwendung nutzt ein modernes Design auf Basis des Minty-Bootswatch-Themes.

## Funktionen
- Registrierung (mit Email) und Login per Benutzername und Passwort
- Generieren von QR-Codes mit Farbe, Hintergrundfarbe und runden Ecken
- Größe der QR-Codes passt sich automatisch dem Inhalt an
- QR-Codes werden pro Benutzer gespeichert
- Download als PNG, JPG oder SVG
- Zu jedem QR-Code kann eine kurze Beschreibung hinterlegt werden
- Vorschau der QR-Codes in der Übersicht

## Pläne

Es gibt mehrere Abomodelle:

Bei jährlicher Zahlung sparst du **30%** auf den Gesamtpreis!

- **Basic** – kostenlos, 1 gespeicherter QR-Code
- **Starter** – 0,99€/Monat oder ~~11,88€~~ **8,32€/Jahr** (**30% sparen!**) für bis zu 5 QR-Codes
- **Pro** – 1,99€/Monat oder ~~23,88€~~ **16,72€/Jahr** (**30% sparen!**) für bis zu 20 QR-Codes
- **Premium** – 4,99€/Monat oder ~~59,88€~~ **41,92€/Jahr** (**30% sparen!**) für bis zu 50 QR-Codes
- **Unlimited** – 9,99€/Monat oder ~~119,88€~~ **83,92€/Jahr** (**30% sparen!**) für unbegrenzte QR-Codes

Die Bezahlung kann über PayPal oder per Kreditkarte via Stripe erfolgen.
Möchtest du deinen Plan wechseln, kündige zunächst das bestehende Abo und wähle anschließend ein neues Modell.

Ein Upgrade von einem günstigeren auf einen teureren Plan ist jederzeit möglich. Die Restlaufzeit des bisherigen Plans wird anteilig gutgeschrieben und auf den neuen Preis angerechnet. Das vorherige Abonnement ist beim Zahlungsdienstleister zu kündigen.

Ein Downgrade von einem höheren auf einen niedrigeren Plan ist nicht möglich.

Eine Kündigung ist jederzeit möglich. Das Abo bleibt jedoch bis zum Ende der bezahlten Laufzeit bestehen; eine Rückerstattung erfolgt nicht.

## Konfiguration

Die Anwendung erwartet die Stripe-API-Schlüssel in den Umgebungsvariablen
`STRIPE_PUBLISHABLE_KEY` und `STRIPE_SECRET_KEY`.

Um auf den Adminbereich zugreifen zu können, muss ein Benutzer als
Administrator markiert sein. Der Benutzer **DO1FFE** ist immer automatisch
Administrator. Weitere Benutzer kannst du nach dem Login über die Admin-Oberfläche
unter "Benutzer bearbeiten" zum Admin machen.

Alternativ lässt sich ein Konto auch direkt per Python-Shell zum Admin
machen:

```python
from app import db, User
u = User.query.filter_by(username="deinname").first()
u.is_admin = True
db.session.commit()
```

