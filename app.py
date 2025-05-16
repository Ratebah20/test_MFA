import os
import json
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = 'selfcare_simulation_secret_key'  # En production, utilisez une clé secrète sécurisée
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Configuration
PORTAIL_API_URL = 'https://acc.portail.orange.lu'
MOCK_API = os.environ.get('MOCK_API', 'false').lower() == 'true'  # Mode réel par défaut

# Fonction de décoration pour les routes qui nécessitent une authentification
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            flash('Vous devez être connecté pour accéder à cette page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Simulation des réponses API (pour les tests sans connectivité au portail réel)
def mock_resolve_otp(otp_token):
    # Si le token contient "invalid", simuler une erreur
    if "invalid" in otp_token:
        return {
            "success": False,
            "message": "Token OTP invalide ou expiré"
        }
    
    # Si le token contient "expired", simuler un token expiré
    if "expired" in otp_token:
        return {
            "success": False,
            "message": "Token OTP expiré"
        }
    
    # Simuler un succès par défaut
    return {
        "success": True,
        "message": "Token OTP validé avec succès",
        "access_token": f"mock_access_token_{otp_token[:5]}",
        "refresh_token": f"mock_refresh_token_{otp_token[:5]}",
        "token_type": "Bearer",
        "expires_in": 3600,
        "user_id": "12345"
    }

# Routes de l'application
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/auth-callback')
def auth_callback():
    """
    Point d'entrée pour la redirection depuis le Portail Orange
    Cette route traite le token OTP reçu via l'URL
    """
    otp_token = request.args.get('otp_token')
    
    if not otp_token:
        flash('Aucun token OTP trouvé dans l\'URL', 'error')
        return redirect(url_for('error', message='missing_token'))
    
    # Passer le token à la page de traitement
    return render_template('processing.html', otp_token=otp_token)

@app.route('/validate-otp', methods=['POST'])
def validate_otp():
    """
    API pour valider le token OTP auprès du serveur MFA
    """
    otp_token = request.json.get('otp_token')
    
    if not otp_token:
        return jsonify({
            "success": False,
            "message": "Token OTP manquant"
        }), 400
    
    try:
        # Appel réel à l'API du Portail Orange
        response = requests.post(
            f"{PORTAIL_API_URL}/resolve-otp",
            json={"otp_token": otp_token, "source": "selfcare"},
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            timeout=10
        )
        response_data = response.json()
        
        # Si la validation est réussie, stocker les tokens en session
        if response_data.get('success'):
            session['access_token'] = response_data.get('access_token')
            session['refresh_token'] = response_data.get('refresh_token')
            session['token_expiry'] = datetime.now().timestamp() + response_data.get('expires_in', 3600)
            session['user_id'] = response_data.get('user_id')
        
        return jsonify(response_data)
    
    except Exception as e:
        app.logger.error(f"Erreur lors de la validation OTP: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Erreur lors de la validation: {str(e)}"
        }), 500

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard accessible uniquement après authentification réussie
    """
    # Calculer le temps restant avant expiration du token
    expiry_time = session.get('token_expiry', 0)
    current_time = datetime.now().timestamp()
    time_remaining = max(0, int(expiry_time - current_time))
    
    return render_template('dashboard.html', 
                          user_id=session.get('user_id'),
                          token_type=session.get('token_type', 'Bearer'),
                          expires_in=time_remaining)

@app.route('/change-password')
def change_password():
    """
    Simulation de la page de changement de mot de passe pour le cas de première connexion
    """
    user_id = request.args.get('userId')
    token = request.args.get('token')
    is_otp = request.args.get('isOTP', 'false').lower() == 'true'
    
    if not user_id or not token:
        flash('Paramètres manquants pour le changement de mot de passe', 'error')
        return redirect(url_for('error', message='missing_params'))
    
    return render_template('change_password.html', 
                          user_id=user_id,
                          token=token,
                          is_otp=is_otp)

@app.route('/set-password', methods=['POST'])
def set_password():
    """
    Traitement du formulaire de changement de mot de passe
    """
    user_id = request.form.get('user_id')
    token = request.form.get('token')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    if not user_id or not token or not password:
        flash('Tous les champs sont obligatoires', 'error')
        return redirect(url_for('change_password', userId=user_id, token=token, isOTP=True))
    
    if password != confirm_password:
        flash('Les mots de passe ne correspondent pas', 'error')
        return redirect(url_for('change_password', userId=user_id, token=token, isOTP=True))
    
    # En production, appeler l'API pour changer le mot de passe
    # Ici, nous simulons juste une réussite
    
    # Après changement réussi, simuler une authentification complète
    session['access_token'] = f"mock_access_token_after_password_change"
    session['refresh_token'] = f"mock_refresh_token_after_password_change"
    session['token_expiry'] = datetime.now().timestamp() + 3600
    session['user_id'] = user_id
    
    flash('Mot de passe défini avec succès', 'success')
    return redirect(url_for('dashboard'))

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
    return render_template('error.html', message=message)

@app.route('/api/user-info')
@login_required
def user_info():
    """
    API simulant la récupération des informations utilisateur
    """
    user_data = {
        "user_id": session.get('user_id', 'unknown'),
        "subscription": "Mobile Premium",
        "status": "Active",
        "created_at": "2023-01-15",
        "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return jsonify(user_data)

@app.route('/simulate-redirect')
def simulate_redirect():
    """
    Simule une redirection depuis le Portail Orange avec un token OTP
    Utile pour les tests sans avoir à passer par le portail réel
    """
    otp_type = request.args.get('type', 'valid')
    
    if otp_type == 'valid':
        otp_token = 'valid_' + os.urandom(16).hex()
    elif otp_type == 'invalid':
        otp_token = 'invalid_' + os.urandom(16).hex()
    elif otp_type == 'expired':
        otp_token = 'expired_' + os.urandom(16).hex()
    else:
        otp_token = os.urandom(16).hex()
    
    redirect_url = url_for('auth_callback', otp_token=otp_token, _external=True)
    return render_template('simulate_redirect.html', redirect_url=redirect_url, otp_token=otp_token)

@app.route('/simulate-first-login')
def simulate_first_login():
    """
    Simule le cas de première connexion avec redirection vers la page de changement de mot de passe
    """
    user_id = 'user_' + os.urandom(4).hex()
    token = 'otp_' + os.urandom(8).hex()
    
    redirect_url = url_for('change_password', userId=user_id, token=token, isOTP=True, _external=True)
    return render_template('simulate_redirect.html', redirect_url=redirect_url, otp_token='')

if __name__ == '__main__':
    # Créer les dossiers templates et static s'ils n'existent pas
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
