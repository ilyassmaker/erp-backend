from django.contrib import admin

from .models import (
    Achat,
    Commande,
    Facture,
    LigneAchat,
    LigneCommande,
    Paiement,
    Person,
    Produit,
    VenteHistorique,
)


class PersonAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "email", "telephone")
    search_fields = ("nom", "email", "telephone")


class ProduitAdmin(admin.ModelAdmin):
    list_display = ("nom", "stock", "prix_achat", "prix_vente")
    search_fields = ("nom",)


class AchatAdmin(admin.ModelAdmin):
    list_display = ("id", "fournisseur", "date_achat", "statut")
    search_fields = ("id", "fournisseur__nom")


class LigneAchatAdmin(admin.ModelAdmin):
    list_display = ("achat", "produit", "quantite", "prix_unitaire")
    search_fields = ("achat__id", "produit__nom")


class CommandeAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "date_commande", "statut")
    search_fields = ("id", "client__nom")


class LigneCommandeAdmin(admin.ModelAdmin):
    list_display = ("commande", "produit", "quantite", "prix_unitaire")
    search_fields = ("commande__id", "produit__nom")


class FactureAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "montant_total",
        "montant_paye",
        "statut",
        "date_facture",
    )
    search_fields = ("id",)


class PaiementAdmin(admin.ModelAdmin):
    list_display = ("id", "facture", "montant", "date_paiement", "methode")
    search_fields = ("facture__id",)


class VenteHistoriqueAdmin(admin.ModelAdmin):
    list_display = ("produit", "mois", "quantite")
    search_fields = ("produit__nom",)


admin.site.register(Person, PersonAdmin)
admin.site.register(Produit, ProduitAdmin)
admin.site.register(Achat, AchatAdmin)
admin.site.register(LigneAchat, LigneAchatAdmin)
admin.site.register(Commande, CommandeAdmin)
admin.site.register(LigneCommande, LigneCommandeAdmin)
admin.site.register(Facture, FactureAdmin)
admin.site.register(Paiement, PaiementAdmin)
admin.site.register(VenteHistorique, VenteHistoriqueAdmin)