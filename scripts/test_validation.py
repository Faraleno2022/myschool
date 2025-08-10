#!/usr/bin/env python
"""
Script de test pour vérifier que la validation des paiements fonctionne correctement
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import Paiement
from django.contrib.auth.models import User
from django.utils import timezone
from django.test import Client
from django.urls import reverse

def test_validation_functionality():
    """Test complet de la fonctionnalité de validation"""
    
    print("🧪 TEST DE LA VALIDATION DES PAIEMENTS")
    print("=" * 50)
    
    # 1. Vérifier les paiements EN_ATTENTE
    print("\n1️⃣ VÉRIFICATION DES PAIEMENTS EN ATTENTE:")
    paiements_attente = Paiement.objects.filter(statut='EN_ATTENTE')
    print(f"   Nombre de paiements EN_ATTENTE: {paiements_attente.count()}")
    
    if paiements_attente.count() == 0:
        print("   ❌ Aucun paiement en attente trouvé pour le test")
        return
    
    # Prendre le premier paiement pour le test
    paiement_test = paiements_attente.first()
    print(f"   Paiement de test: {paiement_test.numero_recu} - {paiement_test.eleve.nom_complet}")
    print(f"   Statut actuel: {paiement_test.statut}")
    print(f"   Validé par: {paiement_test.valide_par}")
    print(f"   Date validation: {paiement_test.date_validation}")
    
    # 2. Vérifier qu'un utilisateur admin existe
    print("\n2️⃣ VÉRIFICATION DES UTILISATEURS:")
    try:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.filter(is_staff=True).first()
        
        if admin_user:
            print(f"   Utilisateur trouvé: {admin_user.username}")
        else:
            print("   ❌ Aucun utilisateur admin trouvé")
            return
    except Exception as e:
        print(f"   ❌ Erreur utilisateur: {e}")
        return
    
    # 3. Test de validation manuelle (simulation)
    print("\n3️⃣ TEST DE VALIDATION MANUELLE:")
    try:
        # Sauvegarder l'état original
        statut_original = paiement_test.statut
        valide_par_original = paiement_test.valide_par
        date_validation_original = paiement_test.date_validation
        
        # Simuler la validation
        paiement_test.statut = 'VALIDE'
        paiement_test.valide_par = admin_user
        paiement_test.date_validation = timezone.now()
        paiement_test.save()
        
        print(f"   ✅ Validation simulée réussie:")
        print(f"      - Nouveau statut: {paiement_test.statut}")
        print(f"      - Validé par: {paiement_test.valide_par.username}")
        print(f"      - Date validation: {paiement_test.date_validation}")
        
        # Restaurer l'état original pour les autres tests
        paiement_test.statut = statut_original
        paiement_test.valide_par = valide_par_original
        paiement_test.date_validation = date_validation_original
        paiement_test.save()
        
        print(f"   ✅ État original restauré")
        
    except Exception as e:
        print(f"   ❌ Erreur lors de la validation: {e}")
    
    # 4. Test de l'URL de validation
    print("\n4️⃣ TEST DE L'URL DE VALIDATION:")
    try:
        url = reverse('paiements:valider_paiement', args=[paiement_test.id])
        print(f"   URL de validation: {url}")
        print(f"   ✅ URL générée correctement")
    except Exception as e:
        print(f"   ❌ Erreur URL: {e}")
    
    # 5. Test avec client Django (simulation de requête POST)
    print("\n5️⃣ TEST DE REQUÊTE POST:")
    try:
        client = Client()
        
        # Connexion avec l'utilisateur admin
        client.force_login(admin_user)
        
        # Requête POST vers l'URL de validation
        response = client.post(url)
        
        print(f"   Code de réponse: {response.status_code}")
        
        if response.status_code == 302:  # Redirection attendue
            print(f"   ✅ Redirection correcte vers: {response.url}")
            
            # Vérifier si le paiement a été validé
            paiement_test.refresh_from_db()
            if paiement_test.statut == 'VALIDE':
                print(f"   ✅ Paiement validé avec succès!")
                print(f"      - Statut: {paiement_test.statut}")
                print(f"      - Validé par: {paiement_test.valide_par.username}")
                print(f"      - Date: {paiement_test.date_validation}")
                
                # Restaurer pour les autres tests
                paiement_test.statut = 'EN_ATTENTE'
                paiement_test.valide_par = None
                paiement_test.date_validation = None
                paiement_test.save()
                print(f"   ✅ État restauré pour les autres tests")
            else:
                print(f"   ❌ Le paiement n'a pas été validé")
        else:
            print(f"   ❌ Code de réponse inattendu: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Erreur requête POST: {e}")
    
    # 6. Résumé final
    print("\n📊 RÉSUMÉ DU TEST:")
    paiements_attente_final = Paiement.objects.filter(statut='EN_ATTENTE')
    paiements_valides = Paiement.objects.filter(statut='VALIDE')
    
    print(f"   - Paiements EN_ATTENTE: {paiements_attente_final.count()}")
    print(f"   - Paiements VALIDÉS: {paiements_valides.count()}")
    
    print("\n🎯 INSTRUCTIONS POUR TEST MANUEL:")
    print("   1. Allez sur: http://127.0.0.1:8000/paiements/liste/?statut=EN_ATTENTE")
    print("   2. Connectez-vous en tant qu'admin")
    print("   3. Cliquez sur le bouton vert ✓ d'un paiement")
    print("   4. Confirmez la validation dans la popup")
    print("   5. Vérifiez que le statut passe à 'Validé'")

if __name__ == '__main__':
    test_validation_functionality()
