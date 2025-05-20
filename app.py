import os
import json
import requests
import logging
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from functools import wraps
import datetime as dt

app = Flask(__name__)

# Configuration des logs plus détaillés
if not app.debug:
    # Configurer le logger pour écrire dans un fichier
    file_handler = logging.FileHandler('error.log')
    file_handler.setLevel(logging.INFO)
    # Format avec horodatage simpli
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

# Configuration de l'application
app.secret_key = os.environ.get('SECRET_KEY', 'selfcare_external_site_key')  # En production, utilisez une clé secrète sécurisée
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Activer le débogage des requêtes pour voir toutes les requêtes entrantes
app.config['DEBUG_REQUESTS'] = True

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
    Détecte également les redirections depuis le MFA avec un token OTP en paramètre
    """
    # Détecter si un token OTP est présent dans l'URL (redirection depuis le Portail Orange)
    otp_token = request.args.get('otp_token') or request.args.get('token') or request.args.get('code')
    
    # Si un token OTP est présent, rediriger vers la route de callback
    if otp_token:
        app.logger.info(f"Détection d'un token OTP dans la route racine, redirection vers auth-callback")
        # Récupérer tous les paramètres pour les transmettre
        params = request.args.copy()
        return redirect(url_for('auth_callback', **params))
    
    # Affichage normal de la page d'accueil si pas de token OTP
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
    # Extraire le token OTP de l'URL (plusieurs paramètres possibles selon la configuration du Portail Orange)
    otp_token = request.args.get('otp_token') or request.args.get('token') or request.args.get('code')
    
    source = request.args.get('source', 'selfcare')
    
    if not otp_token:
        app.logger.warning("Tentative d'accès au callback sans token OTP")
        flash('Aucun token OTP trouvé dans l\'URL. La redirection depuis le Portail Orange est incorrecte.', 'error')
        return redirect(url_for('error_page', message='missing_token'))
    
    # Masquer partiellement le token dans les logs pour des raisons de sécurité
    masked_token = f"{otp_token[:8]}...{otp_token[-4:] if len(otp_token) > 12 else ''}"
    app.logger.info(f"Redirection reçue avec token OTP: {masked_token} (source: {source})")
    
    # Activer la validation automatique côté serveur pour éviter les problèmes avec AJAX
    try:
        # Valider directement le token avec l'API du Portail Orange
        app.logger.info(f"Tentative de validation automatique du token côté serveur")
        result = validate_token_with_api(otp_token, source)
        app.logger.info(f"Résultat de validation: {result.get('success')}, message: {result.get('message', 'Aucun message')}")
        
        if result.get('success'):
            # Stocker les informations d'authentification dans la session
            session['access_token'] = result.get('access_token')
            session['refresh_token'] = result.get('refresh_token', '')
            session['token_type'] = result.get('token_type', 'Bearer')
            session['token_expiry'] = datetime.now().timestamp() + result.get('expires_in', 3600)
            session['user_id'] = result.get('user_id')
            
            app.logger.info(f"Authentification réussie pour l'utilisateur {result.get('user_id')}")
            
            # Passer le token à la page de traitement avec le résultat de validation
            return render_template('processing.html', 
                                otp_token=otp_token, 
                                source=source,
                                validation_result=result,  # Passer le résultat à la page
                                auto_validated=True,       # Indiquer que validation déjà faite
                                redirect_to_dashboard=True, # Rediriger après affichage
                                user_id=result.get('user_id'),
                                expires_in=result.get('expires_in', 3600),
                                mfa_login_url=MFA_LOGIN_URL,
                                PORTAIL_API_URL=PORTAIL_API_URL,
                                now=dt.datetime.now())
        else:
            # En cas d'échec, montrer la page de traitement avec l'erreur
            app.logger.warning(f"Validation OTP échouée: {result.get('message')}")
            return render_template('processing.html', 
                                otp_token=otp_token, 
                                source=source,
                                validation_result=result,  # Passer le résultat à la page
                                auto_validated=True,      # Indiquer que validation déjà faite
                                error_message=result.get('message', 'Échec de validation du token OTP.'),
                                mfa_login_url=MFA_LOGIN_URL,
                                PORTAIL_API_URL=PORTAIL_API_URL,
                                now=dt.datetime.now())
    except Exception as e:
        app.logger.error(f"Erreur lors de la validation automatique du token OTP: {str(e)}")
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        
        # En cas d'erreur durant la validation, afficher la page de traitement standard
        # pour permettre la validation côté client
        return render_template('processing.html', 
                              otp_token=otp_token, 
                              source=source,
                              mfa_login_url=MFA_LOGIN_URL,
                              PORTAIL_API_URL=PORTAIL_API_URL,
                              now=dt.datetime.now())

def validate_token_with_api(otp_token, source='selfcare'):
    """
    Fonction utilitaire pour valider un token OTP auprès du Portail Orange API
    """
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
            return {
                "success": False,
                "message": f"Erreur lors de la communication avec le Portail Orange: {response.status_code}"
            }
        
        # Traiter la réponse JSON
        try:
            response_data = response.json()
            return response_data
        except ValueError:
            app.logger.error("Réponse invalide du Portail Orange (JSON invalide)")
            return {
                "success": False,
                "message": "Réponse invalide du serveur d'authentification"
            }
            
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur de connexion lors de la validation OTP: {str(e)}")
        return {
            "success": False,
            "message": f"Impossible de se connecter au serveur d'authentification: {str(e)}"
        }
    except Exception as e:
        app.logger.error(f"Erreur inattendue lors de la validation OTP: {str(e)}")
        return {
            "success": False,
            "message": f"Une erreur inattendue s'est produite: {str(e)}"
        }

@app.route('/validate-otp', methods=['POST'])
def validate_otp():
    """
    Endpoint pour valider un token OTP (déprécié)
    Cet endpoint est conservé pour la compatibilité arrière, mais la validation est maintenant
    effectuée directement par le navigateur client.
    """
    app.logger.info(f"Requête POST reçue sur /validate-otp avec Content-Type: {request.headers.get('Content-Type')}")
    
    try:
        # Vérifier le format de la requête
        if not request.is_json:
            app.logger.error(f"Requête non-JSON reçue: {request.data[:100]}")
            return jsonify({
                "success": False,
                "message": "Format de requête invalide, JSON attendu"
            }), 400
        
        # Récupérer les données
        data = request.json
        otp_token = data.get('otp_token')
        
        if not otp_token:
            app.logger.warning("Tentative de validation sans token OTP")
            return jsonify({
                'success': False,
                'message': "Aucun token OTP n'a été fourni"
            }), 400
        
        # Informer que cet endpoint est déprécié
        app.logger.info("L'endpoint /validate_otp est déprécié. Utilisez plutôt la validation directe côté client.")
        
        return jsonify({
            "success": False,
            "message": "Cet endpoint est déprécié. La validation OTP doit maintenant être effectuée directement par le client.",
            "deprecated": True
        }), 400
    
    except Exception as e:
        # Capturer toutes les erreurs possibles
        app.logger.error(f"Exception lors de la validation OTP: {str(e)}")
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "message": f"Erreur serveur lors de la validation: {str(e)}"
        }), 500

@app.route('/validation-success', methods=['POST'])
def validation_success():
    """
    Endpoint pour traiter le résultat de validation réussie transmis par le frontend
    Après validation réussie du token OTP directement avec le Portail Orange,
    le client informe le backend du résultat pour mettre à jour la session.
    """
    app.logger.info(f"Requête POST reçue sur /validation-success avec Content-Type: {request.headers.get('Content-Type')}")
    
    try:
        # Vérifier le format de la requête
        if not request.is_json:
            app.logger.error(f"Requête non-JSON reçue: {request.data[:100]}")
            return jsonify({
                "success": False,
                "message": "Format de requête invalide, JSON attendu"
            }), 400
        
        # Récupérer les données
        data = request.json
        app.logger.info(f"Données reçues du client pour la validation réussie")
        
        validation_result = data.get('validation_result', False)
        user_id = data.get('user_id', '')
        auth_data = data.get('auth_data', {})
        
        if not validation_result:
            app.logger.warning("Validation OTP échouée transmise par le frontend")
            return jsonify({
                'success': False,
                'message': "La validation du token OTP a échoué"
            }), 400
        
        # Stocker l'authentification réussie dans la session
        session['authenticated'] = True
        session['auth_time'] = dt.datetime.now().isoformat()
        session['user_id'] = user_id or "user_123"  # Utiliser l'ID fourni ou une valeur par défaut
        
        # Si nous avons des données d'authentification, les stocker également
        if auth_data:
            # Masquer les tokens pour le log
            masked_auth = auth_data.copy() if isinstance(auth_data, dict) else {}
            if 'access_token' in masked_auth:
                masked_auth['access_token'] = f"{masked_auth['access_token'][:8]}..." if masked_auth['access_token'] else ''
            if 'refresh_token' in masked_auth:
                masked_auth['refresh_token'] = f"{masked_auth['refresh_token'][:8]}..." if masked_auth['refresh_token'] else ''
            
            app.logger.info(f"Données d'authentification reçues: {masked_auth}")
            session['auth_data'] = auth_data
        
        app.logger.info(f"Validation OTP réussie pour l'utilisateur {user_id}, session authentifiée")
        return jsonify({
            'success': True,
            'message': "Session authentifiée avec succès",
            'redirect': url_for('dashboard')
        })
        
    except Exception as e:
        # Capturer toutes les erreurs possibles
        app.logger.error(f"Exception lors du traitement de la validation réussie: {str(e)}")
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "message": f"Erreur serveur lors du traitement de la validation réussie: {str(e)}"
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
        return redirect(url_for('error_page', message='missing_params'))
    
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

# Route pour la page d'erreur
@app.route('/error-page')
def error_page():
    """
    Page d'erreur qui affiche des informations détaillées sur les erreurs d'authentification
    Le paramètre 'message' identifie le type d'erreur à afficher
    """
    # Récupérer le message d'erreur depuis les paramètres
    error_message = request.args.get('message', 'unknown_error')
    error_code = request.args.get('code', 'ERR_UNKNOWN')
    request_id = str(uuid.uuid4())[:8]  # Générer un ID unique pour cette erreur
    
    app.logger.warning(f"Affichage de la page d'erreur: {error_message} (code: {error_code}, request_id: {request_id})")
    
    # Dans un environnement de développement, on montre le bouton de simulation
    show_debug_button = app.debug or os.environ.get('SHOW_DEBUG_TOOLS') == 'true'
    
    # Rendre le template avec les informations d'erreur
    return render_template('error.html', 
                          message=error_message,
                          error_code=error_code,
                          request_id=request_id,
                          show_debug_button=show_debug_button,
                          mfa_login_url=MFA_LOGIN_URL,
                          now=dt.datetime.now())

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
