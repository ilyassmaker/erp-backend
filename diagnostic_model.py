# test_model_comprehensive.py - Script complet pour tester le modèle de risque
# Exécuter avec: python manage.py shell < test_model_comprehensive.py

import joblib
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

# Configuration
model_path = Path("erp_app/ml/model_risque_facture_simple.joblib")
print("=== Test Complet du Modèle de Risque Client ===\n")

# Charger le modèle
if not model_path.exists():
    print(f"❌ ERREUR: Le modèle n'existe pas à {model_path}")
    exit(1)

model = joblib.load(model_path)
print("✅ Modèle chargé avec succès\n")

# Créer un dataset de test synthétique
def generate_test_data():
    """Génère des données de test variées pour évaluer le modèle"""
    
    np.random.seed(42)
    n_samples = 100
    
    # Générer des profils variés
    data = []
    
    # 1. Clients à risque faible (33%)
    for _ in range(33):
        data.append({
            'montant_total': np.random.uniform(1000, 50000),
            'nb_relances': np.random.choice([0, 1], p=[0.8, 0.2]),
            'delai_paiement': np.random.uniform(0, 20),
            'nb_commandes_client': np.random.randint(10, 100),
            'total_achats_client': np.random.uniform(10000, 500000),
            'moyenne_retard_client': np.random.uniform(0, 10),
            'type_client': 'client',
            'expected_risk': 'faible'
        })
    
    # 2. Clients à risque modéré (34%)
    for _ in range(34):
        data.append({
            'montant_total': np.random.uniform(500, 20000),
            'nb_relances': np.random.choice([1, 2, 3], p=[0.5, 0.3, 0.2]),
            'delai_paiement': np.random.uniform(20, 60),
            'nb_commandes_client': np.random.randint(3, 30),
            'total_achats_client': np.random.uniform(5000, 100000),
            'moyenne_retard_client': np.random.uniform(10, 40),
            'type_client': 'client',
            'expected_risk': 'modéré'
        })
    
    # 3. Clients à risque élevé (33%)
    for _ in range(33):
        data.append({
            'montant_total': np.random.uniform(100, 30000),
            'nb_relances': np.random.choice([3, 4, 5, 6, 7, 8], p=[0.2, 0.2, 0.2, 0.2, 0.1, 0.1]),
            'delai_paiement': np.random.uniform(60, 180),
            'nb_commandes_client': np.random.randint(1, 10),
            'total_achats_client': np.random.uniform(1000, 50000),
            'moyenne_retard_client': np.random.uniform(40, 120),
            'type_client': 'client',
            'expected_risk': 'élevé'
        })
    
    return pd.DataFrame(data)

# Générer les données
print("=== Génération des données de test ===")
test_df = generate_test_data()
print(f"✅ {len(test_df)} échantillons générés\n")

# Faire les prédictions
features = ['montant_total', 'nb_relances', 'delai_paiement', 
           'nb_commandes_client', 'total_achats_client', 'moyenne_retard_client', 'type_client']
X_test = test_df[features]

predictions = model.predict(X_test)
test_df['prediction'] = predictions
test_df['prediction_label'] = test_df['prediction'].map({
    0: 'élevé', 
    1: 'modéré', 
    2: 'faible'
})

# Obtenir les probabilités
if hasattr(model, 'predict_proba'):
    probas = model.predict_proba(X_test)
    test_df['proba_impayee'] = probas[:, 0]
    test_df['proba_partielle'] = probas[:, 1]
    test_df['proba_payee'] = probas[:, 2]
    test_df['confidence'] = probas.max(axis=1)

# Afficher des statistiques
print("=== Résultats des Prédictions ===")
print(f"\nDistribution des prédictions:")
print(test_df['prediction_label'].value_counts())
print(f"\nConfiance moyenne: {test_df['confidence'].mean():.2%}")

# Analyser les features importantes
print("\n=== Analyse des Features par Niveau de Risque ===")
for risk_level in ['faible', 'modéré', 'élevé']:
    subset = test_df[test_df['prediction_label'] == risk_level]
    if len(subset) > 0:
        print(f"\n{risk_level.upper()} (n={len(subset)}):")
        print(f"  - Nb relances moyen: {subset['nb_relances'].mean():.1f}")
        print(f"  - Délai paiement moyen: {subset['delai_paiement'].mean():.0f} jours")
        print(f"  - Retard moyen: {subset['moyenne_retard_client'].mean():.0f} jours")
        print(f"  - Nb commandes moyen: {subset['nb_commandes_client'].mean():.0f}")
        print(f"  - Montant moyen: {subset['montant_total'].mean():,.0f} €")

# Identifier les cas limites
print("\n=== Cas Limites (Confiance < 50%) ===")
low_confidence = test_df[test_df['confidence'] < 0.5]
if len(low_confidence) > 0:
    for idx, row in low_confidence.head(5).iterrows():
        print(f"\nCas {idx}:")
        print(f"  Prédiction: {row['prediction_label']}")
        print(f"  Probabilités: impayée={row['proba_impayee']:.1%}, "
              f"partielle={row['proba_partielle']:.1%}, payée={row['proba_payee']:.1%}")
        print(f"  Features: relances={row['nb_relances']}, "
              f"délai={row['delai_paiement']:.0f}j, retard={row['moyenne_retard_client']:.0f}j")
else:
    print("Aucun cas avec confiance < 50%")

# Créer des visualisations si matplotlib est disponible
try:
    # Configuration des graphiques
    plt.style.use('seaborn-v0_8-darkgrid')
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Analyse du Modèle de Risque Client', fontsize=16)
    
    # 1. Distribution des prédictions
    ax1 = axes[0, 0]
    test_df['prediction_label'].value_counts().plot(kind='bar', ax=ax1, color=['green', 'orange', 'red'])
    ax1.set_title('Distribution des Niveaux de Risque')
    ax1.set_xlabel('Niveau de Risque')
    ax1.set_ylabel('Nombre de Clients')
    
    # 2. Relation entre nb_relances et délai_paiement
    ax2 = axes[0, 1]
    colors = {0: 'red', 1: 'orange', 2: 'green'}
    for pred in [0, 1, 2]:
        subset = test_df[test_df['prediction'] == pred]
        ax2.scatter(subset['nb_relances'], subset['delai_paiement'], 
                   c=colors[pred], label=subset.iloc[0]['prediction_label'] if len(subset) > 0 else '',
                   alpha=0.6)
    ax2.set_xlabel('Nombre de Relances')
    ax2.set_ylabel('Délai de Paiement (jours)')
    ax2.set_title('Relances vs Délai de Paiement')
    ax2.legend()
    
    # 3. Distribution de la confiance
    ax3 = axes[1, 0]
    test_df['confidence'].hist(bins=20, ax=ax3, color='skyblue', edgecolor='black')
    ax3.axvline(test_df['confidence'].mean(), color='red', linestyle='--', 
                label=f'Moyenne: {test_df["confidence"].mean():.2%}')
    ax3.set_xlabel('Confiance de la Prédiction')
    ax3.set_ylabel('Fréquence')
    ax3.set_title('Distribution de la Confiance du Modèle')
    ax3.legend()
    
    # 4. Features moyennes par niveau de risque
    ax4 = axes[1, 1]
    risk_stats = test_df.groupby('prediction_label')[['nb_relances', 'delai_paiement', 'moyenne_retard_client']].mean()
    risk_stats.plot(kind='bar', ax=ax4)
    ax4.set_title('Features Moyennes par Niveau de Risque')
    ax4.set_xlabel('Niveau de Risque')
    ax4.set_ylabel('Valeur Moyenne')
    ax4.legend(['Nb Relances', 'Délai Paiement', 'Retard Moyen'])
    
    plt.tight_layout()
    plt.savefig('analyse_modele_risque.png', dpi=150, bbox_inches='tight')
    print("\n✅ Graphiques sauvegardés dans 'analyse_modele_risque.png'")
    
except Exception as e:
    print(f"\n⚠️ Impossible de créer les graphiques: {e}")

# Recommandations basées sur l'analyse
print("\n=== Recommandations ===")
print("1. Seuils d'alerte identifiés:")
print(f"   - Plus de 3 relances → Risque élevé probable")
print(f"   - Délai > 60 jours → Surveillance accrue")
print(f"   - Nouveau client (< 3 commandes) → Évaluation prudente")

print("\n2. Actions suggérées par niveau:")
print("   - Risque FAIBLE: Conditions normales, possibilité d'augmenter les limites")
print("   - Risque MODÉRÉ: Suivi rapproché, relances préventives")
print("   - Risque ÉLEVÉ: Paiement d'avance, garanties supplémentaires")

print("\n✅ Test complet terminé!")

# Sauvegarder les résultats
test_df.to_csv('resultats_test_modele.csv', index=False)
print("📊 Résultats détaillés sauvegardés dans 'resultats_test_modele.csv'")