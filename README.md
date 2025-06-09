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

- **Basic** – kostenlos, 1 gespeicherter QR-Code
- **Starter** – 1,99€/Monat für bis zu 5 QR-Codes
- **Pro** – 4,99€/Monat für bis zu 20 QR-Codes
- **Premium** – 9,99€/Monat für bis zu 50 QR-Codes
- **Unlimited** – 19,99€/Monat für unbegrenzte QR-Codes

Die Bezahlung kann über PayPal oder per Kreditkarte via Stripe erfolgen.
Möchtest du deinen Plan wechseln, kündige zunächst das bestehende Abo und wähle anschließend ein neues Modell.

## Konfiguration

Die Anwendung erwartet die Stripe-API-Schlüssel in den Umgebungsvariablen
`STRIPE_PUBLISHABLE_KEY` und `STRIPE_SECRET_KEY`.
