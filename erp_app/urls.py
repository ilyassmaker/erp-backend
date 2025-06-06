from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    PersonViewSet, ProduitViewSet, AchatViewSet, LigneAchatViewSet,
    CommandeViewSet, LigneCommandeViewSet, FactureViewSet, PaiementViewSet,
    CompteBancaireViewSet,TransactionTresorerieViewSet,RelancePaiementViewSet,
    home,download_facture_pdf
)

router = DefaultRouter()
router.register(r'persons', PersonViewSet, basename='person')
router.register(r'produits', ProduitViewSet)
router.register(r'achats', AchatViewSet)
router.register(r'ligneachats', LigneAchatViewSet)
router.register(r'commandes', CommandeViewSet)
router.register(r'lignecommandes', LigneCommandeViewSet)
router.register(r'factures', FactureViewSet)
router.register(r'paiements', PaiementViewSet)
router.register(r'comptes-bancaires', CompteBancaireViewSet)
router.register(r'transactions-tresorerie', TransactionTresorerieViewSet)
router.register(r'relances-paiement', RelancePaiementViewSet)

urlpatterns = [
    path('', home),
    path('api/', include(router.urls)),
    path('api/factures/<int:pk>/pdf/', download_facture_pdf, name='facture-pdf'),  # ✅ ici
]
