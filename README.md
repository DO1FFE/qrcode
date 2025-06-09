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
- **Starter** – 2,49€/Monat oder 20,92€/Jahr (**30% sparen!**) für bis zu 5 QR-Codes
- **Pro** – 5,99€/Monat oder 50,32€/Jahr (**30% sparen!**) für bis zu 20 QR-Codes
- **Premium** – 11,99€/Monat oder 100,72€/Jahr (**30% sparen!**) für bis zu 50 QR-Codes
- **Unlimited** – 23,99€/Monat oder 201,52€/Jahr (**30% sparen!**) für unbegrenzte QR-Codes

Die Bezahlung kann über PayPal oder per Kreditkarte via Stripe erfolgen.
Möchtest du deinen Plan wechseln, kündige zunächst das bestehende Abo und wähle anschließend ein neues Modell.

## Konfiguration

Die Anwendung erwartet die Stripe-API-Schlüssel in den Umgebungsvariablen
`STRIPE_PUBLISHABLE_KEY` und `STRIPE_SECRET_KEY`.
