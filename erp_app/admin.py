from django.contrib import admin
from .models import Person, Produit, Achat, LigneAchat, Commande, LigneCommande, Facture, Paiement

admin.site.register(Person)
admin.site.register(Produit)
admin.site.register(Achat)
admin.site.register(LigneAchat)
admin.site.register(Commande)
admin.site.register(LigneCommande)
admin.site.register(Facture)
admin.site.register(Paiement)
