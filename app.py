import os
import json
import requests
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from functools import wraps
import datetime as dt

app = Flask(__name__)

# Configuration de l'application
app.secret_key = os.environ.get('SECRET_KEY', 'selfcare_external_site_key')  # En production, utilisez une clé secrète sécurisée
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Configuration de l'intégration avec Portail Orange
PORTAIL_API_URL = os.environ.get('PORTAIL_API_URL', 'https://acc.portail.orange.lu')
MFA_LOGIN_URL = f"{PORTAIL_API_URL}/login"  # URL de connexion au MFA
OTP_RESOLVE_ENDPOINT = f"{PORTAIL_API_URL}/resolve-otp"  # Endpoint pour valider les tokens OTP

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    filemode='a'
)

# Fonction de décoration pour les routes qui nécessitent une authentification
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            flash('Vous devez être connecté via le Portail Orange pour accéder à cette page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Routes de l'application
@app.route('/')
def index():
    """
    Page d'accueil avec lien vers le Portail Orange pour débuter l'authentification
    """
    app.logger.info("Accès à la page d'accueil")
    return render_template('index.html', 
                          mfa_login_url=MFA_LOGIN_URL,
                          PORTAIL_API_URL=PORTAIL_API_URL,
                          now=dt.datetime.now())

@app.route('/auth-callback')
def auth_callback():
    """
    Point d'entrée pour la redirection depuis le Portail Orange
    Cette route traite le token OTP reçu via l'URL
    """
    otp_token = request.args.get('otp_token')
    
    if not otp_token:
        app.logger.warning("Tentative d'accès au callback sans token OTP")
        flash('Aucun token OTP trouvé dans l\'URL. La redirection depuis le Portail Orange est incorrecte.', 'error')
        return redirect(url_for('error', message='missing_token'))
    
    app.logger.info(f"Redirection reçue avec token OTP: {otp_token[:8]}...")
    
    # Passer le token à la page de traitement
    return render_template('processing.html', 
                          otp_token=otp_token, 
                          mfa_login_url=MFA_LOGIN_URL,
                          PORTAIL_API_URL=PORTAIL_API_URL,
                          now=dt.datetime.now())

@app.route('/validate-otp', methods=['POST'])
def validate_otp():
    """
    API pour valider le token OTP auprès du serveur MFA
    Cette fonction représente le cœur de l'intégration entre Selfcare et le Portail Orange
    """
    data = request.json
    otp_token = data.get('otp_token')
    source = data.get('source', 'selfcare')
    
    if not otp_token:
        app.logger.warning("Tentative de validation sans token OTP")
        return jsonify({
            "success": False,
            "message": "Token OTP manquant"
        }), 400
    
    # Tronquer le token pour les logs pour des raisons de sécurité
    masked_token = f"{otp_token[:8]}...{otp_token[-4:] if len(otp_token) > 12 else ''}" 
    app.logger.info(f"Validation du token OTP {masked_token} auprès de {OTP_RESOLVE_ENDPOINT}")
    
    try:
        # Appel à l'API du Portail Orange pour valider le token OTP
        response = requests.post(
            OTP_RESOLVE_ENDPOINT,
            json={
                "otp_token": otp_token, 
                "source": source
            },
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            timeout=10
        )
        
        # Journaliser la réponse (code HTTP uniquement)
        app.logger.info(f"Réponse du Portail Orange: HTTP {response.status_code}")
        
        if response.status_code != 200:
            app.logger.error(f"Erreur HTTP {response.status_code} lors de la validation OTP: {response.text}")
            return jsonify({
                "success": False,
                "message": f"Erreur lors de la communication avec le Portail Orange: {response.status_code}"
            }), 500
            
        # Traiter la réponse JSON
        try:
            response_data = response.json()
        except ValueError:
            app.logger.error("Réponse invalide du Portail Orange (JSON invalide)")
            return jsonify({
                "success": False,
                "message": "Réponse invalide du serveur d'authentification"
            }), 500
        
        # Si la validation est réussie, stocker les tokens en session
        if response_data.get('success'):
            # Stocker les informations d'authentification dans la session
            session['access_token'] = response_data.get('access_token')
            session['refresh_token'] = response_data.get('refresh_token')
            session['token_type'] = response_data.get('token_type', 'Bearer')
            session['token_expiry'] = datetime.now().timestamp() + response_data.get('expires_in', 3600)
            session['user_id'] = response_data.get('user_id')
            
            app.logger.info(f"Authentification réussie pour l'utilisateur {response_data.get('user_id')}")
        else:
            app.logger.warning(f"Validation OTP échouée: {response_data.get('message')}")
        
        return jsonify(response_data)
    
    except requests.exceptions.RequestException as e:
        # Erreur de connexion ou timeout
        app.logger.error(f"Erreur de connexion lors de la validation OTP: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Impossible de se connecter au serveur d'authentification. Veuillez réessayer."
        }), 503
    except Exception as e:
        # Autres erreurs
        app.logger.error(f"Erreur inattendue lors de la validation OTP: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Une erreur inattendue s'est produite. Veuillez réessayer ultérieurement."
        }), 500

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard accessible uniquement après authentification réussie via le Portail Orange
    Cette page représente ce que l'utilisateur verrait après une authentification réussie
    """
    # Calculer le temps restant avant expiration du token
    expiry_time = session.get('token_expiry', 0)
    current_time = datetime.now().timestamp()
    time_remaining = max(0, int(expiry_time - current_time))
    
    app.logger.info(f"Accès au dashboard pour l'utilisateur {session.get('user_id')}")
    
    return render_template('dashboard.html', 
                          user_id=session.get('user_id'),
                          token_type=session.get('token_type', 'Bearer'),
                          access_token=session.get('access_token', '')[:10] + '...',
                          expires_in=time_remaining,
                          mfa_login_url=MFA_LOGIN_URL,
                          now=dt.datetime.now())

@app.route('/change-password')
def change_password():
    """
    Page de changement de mot de passe pour le cas de première connexion
    Cette route est utilisée lors d'une redirection spéciale pour les nouveaux utilisateurs
    """
    user_id = request.args.get('userId')
    token = request.args.get('token')
    is_otp = request.args.get('isOTP', 'false').lower() == 'true'
    
    if not user_id or not token:
        flash('Paramètres manquants pour le changement de mot de passe', 'error')
        return redirect(url_for('error', message='missing_params'))
    
    app.logger.info(f"Accès à la page de changement de mot de passe pour l'utilisateur {user_id} avec token {token[:5]}...")
    return render_template('change_password.html', 
                          user_id=user_id,
                          token=token,
                          is_otp=is_otp,
                          now=dt.datetime.now())

@app.route('/logout')
def logout():
    """
    Déconnexion: nettoyer la session
    """
    session.clear()
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('index'))

@app.route('/error')
def error():
    """
    Page d'erreur générique
    """
    message = request.args.get('message', 'unknown_error')
    return render_template('error.html', message=message, now=dt.datetime.now())

@app.route('/api/user-info')
@login_required
def user_info():
    """
    API qui utiliserait les tokens d'authentification pour récupérer 
    les informations utilisateur depuis les services Orange
    """
    # Dans une implémentation réelle, vous utiliseriez l'access_token pour
    # appeler les API d'Orange et récupérer les informations utilisateur
    user_data = {
        "user_id": session.get('user_id', 'unknown'),
        "subscription": "Mobile Premium",
        "status": "Active",
        "created_at": "2023-01-15",
        "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return jsonify(user_data)

# Route pour la page de démonstration du processus de redirection
@app.route('/demo-redirect')
def demo_redirect():
    """
    Cette page permet de démontrer le processus de redirection
    En production, la redirection viendrait du Portail Orange, pas de cette page
    """
    app.logger.info("Accès à la page de démonstration du processus de redirection")
    return render_template('demo_redirect.html', 
                          mfa_login_url=MFA_LOGIN_URL,
                          PORTAIL_API_URL=PORTAIL_API_URL,
                          now=dt.datetime.now())

if __name__ == '__main__':
    # S'assurer que les dossiers nécessaires existent
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Configurer les variables d'environnement par défaut si elles ne sont pas définies
    if not os.environ.get('PORTAIL_API_URL'):
        app.logger.warning("PORTAIL_API_URL non défini dans l'environnement, utilisation de la valeur par défaut")
    
    # Informations de démarrage
    app.logger.info(f"Démarrage de l'application Selfcare OTP Integration Demo")
    app.logger.info(f"Portail Orange API URL: {PORTAIL_API_URL}")
    app.logger.info(f"MFA Login URL: {MFA_LOGIN_URL}")
    
    # Démarrer le serveur
    port = int(os.environ.get('PORT', 5000))
    app.logger.info(f"Serveur démarré sur le port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
