
from datetime import date, timedelta

from django.db import models
from django.db.models import Sum


class Person(models.Model):
    TYPE_CHOICES = (
        ("client", "Client"),
        ("fournisseur", "Fournisseur"),
    )

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    nom = models.CharField(max_length=100)
    email = models.EmailField()
    telephone = models.CharField(max_length=20)
    adresse = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nom} ({self.get_type_display()})"


class Produit(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    stock = models.PositiveIntegerField(default=0) 
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2)
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.nom


# ---------------------------------------------------------------------------
#  ACHATS
# ---------------------------------------------------------------------------
class Achat(models.Model):
    STATUT_CHOICES = [
        ("en attente", "En attente"),
        ("en cours", "En cours"),
        ("livrée", "Livrée"),
        ("annulée", "Annulée"),
    ]

    fournisseur = models.ForeignKey(
        Person, limit_choices_to={"type": "fournisseur"}, on_delete=models.CASCADE
    )
    date_achat = models.DateField(auto_now_add=True)
    statut = models.CharField(max_length=50, choices=STATUT_CHOICES, default="en attente")

    def __str__(self):
        return f"Achat #{self.id} - {self.statut}"


class LigneAchat(models.Model):
    achat = models.ForeignKey(Achat, related_name="lignes", on_delete=models.CASCADE)
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.produit} x {self.quantite}"


# ---------------------------------------------------------------------------
#  COMMANDES
# ---------------------------------------------------------------------------
class Commande(models.Model):
    STATUT_CHOICES = [
        ("en attente", "En attente"),
        ("en cours", "En cours"),
        ("livrée", "Livrée"),
        ("annulée", "Annulée"),
    ]

    client = models.ForeignKey(
        Person, limit_choices_to={"type": "client"}, on_delete=models.CASCADE
    )
    date_commande = models.DateField(auto_now_add=True)
    statut = models.CharField(max_length=50, choices=STATUT_CHOICES, default="en attente")

    def __str__(self):
        return f"Commande #{self.id} - {self.statut}"


class LigneCommande(models.Model):
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE)
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.produit} x {self.quantite}"


# ---------------------------------------------------------------------------
#  FACTURES
# ---------------------------------------------------------------------------
class Facture(models.Model):
    STATUT_CHOICES = [
        ("impayée", "Impayée"),
        ("partielle", "Partiellement payée"),
        ("payée", "Payée"),
    ]

    commande = models.OneToOneField(Commande, on_delete=models.CASCADE, null=True, blank=True)
    achat = models.OneToOneField(Achat, on_delete=models.CASCADE, null=True, blank=True)

    montant_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_paye = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    date_facture = models.DateField(auto_now_add=True)
    date_echeance_restant = models.DateField(null=True, blank=True)

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="impayée")

    commande_lignes = models.ManyToManyField(
        LigneCommande, blank=True, related_name="factures"
    )
    achat_lignes = models.ManyToManyField(
        LigneAchat, blank=True, related_name="factures"
    )

    def __str__(self):
        return f"Facture #{self.id} - {self.statut}"


# ---------------------------------------------------------------------------
#  COMPTES BANCAIRES & TRÉSORERIE
# ---------------------------------------------------------------------------
class CompteBancaire(models.Model):
    nom_banque = models.CharField(max_length=100)
    numero_compte = models.CharField(max_length=50)
    description = models.CharField(max_length=100, blank=True)
    est_actif = models.BooleanField(default=True)
    solde = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.nom_banque} - {self.numero_compte}"


class TransactionTresorerie(models.Model):
    TYPE_CHOICES = (("entrée", "Entrée"), ("sortie", "Sortie"))

    compte = models.ForeignKey(CompteBancaire, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_transaction = models.DateField(auto_now_add=True)
    description = models.TextField(blank=True)

    facture = models.ForeignKey(Facture, on_delete=models.SET_NULL, null=True, blank=True)
    paiement = models.ForeignKey("Paiement", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        compte = f"({self.compte})" if self.compte else ""
        return f"{self.type} - {self.montant} DH le {self.date_transaction} {compte}"


# ---------------------------------------------------------------------------
#  PAIEMENTS
# ---------------------------------------------------------------------------
class Paiement(models.Model):
    METHODE_CHOICES = [
        ("espèce", "Espèce"),
        ("virement", "Virement"),
        ("chèque", "Chèque"),
    ]

    facture = models.ForeignKey(Facture, on_delete=models.CASCADE)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_paiement = models.DateField(auto_now_add=True)
    methode = models.CharField(max_length=50, choices=METHODE_CHOICES, default="espèce")
    compte_bancaire = models.ForeignKey(CompteBancaire, on_delete=models.SET_NULL, null=True, blank=True)
    reference_paiement = models.CharField(max_length=100, blank=True)
    paiement_complet    = models.BooleanField(default=True)
    date_echeance_solde = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Paiement {self.montant} DH facture {self.facture_id}"

    # ------------------------------------------------------------
    # Logique de cascade : trésorerie + mise à jour facture/statut
    # ------------------------------------------------------------
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        # Créer la ligne de trésorerie à la création
        if is_new and self.compte_bancaire:
            # Déterminer sens du flux
            if self.facture.commande:
                t_type = "entrée"  # client paie -> argent entre
            elif self.facture.achat:
                t_type = "sortie"  # on paie fournisseur -> argent sort
            else:
                t_type = "entrée"

            TransactionTresorerie.objects.create(
                compte=self.compte_bancaire,
                type=t_type,
                montant=self.montant,
                description=f"Paiement pour facture #{self.facture.id}",
                paiement=self,
                facture=self.facture,
            )

            # Mise à jour solde compte
            if t_type == "entrée":
                self.compte_bancaire.solde += self.montant
            else:
                self.compte_bancaire.solde -= self.montant
            self.compte_bancaire.save(update_fields=["solde"])

        # ---------------------------------------------
        #   Mettre à jour montant_paye + statut facture
        # ---------------------------------------------
        total_paye = self.facture.paiement_set.aggregate(total=Sum("montant"))["total"] or 0
        self.facture.montant_paye = total_paye

        reste = self.facture.montant_total - total_paye
        if reste <= 0:
            self.facture.statut = "payée"
            self.facture.date_echeance_restant = None
        else:
            self.facture.statut = "partielle" if total_paye > 0 else "impayée"
            # si aucun échéancier défini, propose +7 jours par défaut
            if not self.facture.date_echeance_restant:
                self.facture.date_echeance_restant = date.today() + timedelta(days=7)

        self.facture.save(update_fields=["montant_paye", "statut", "date_echeance_restant"])


# ---------------------------------------------------------------------------
#  RELANCES PAIEMENT
# ---------------------------------------------------------------------------
class RelancePaiement(models.Model):
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name="relances")
    date_relance = models.DateField(auto_now_add=True)
    statut = models.CharField(max_length=20, default="envoyée")  # envoyée / réglée
    numero = models.PositiveSmallIntegerField(default=1)
    note = models.TextField(blank=True)

    def __str__(self):
        return f"Relance #{self.numero} facture {self.facture_id}"


# ---------------------------------------------------------------------------
#  CONFIGURATION ERP (singleton)
# ---------------------------------------------------------------------------
class ConfigurationERP(models.Model):
    utiliser_comptes_bancaires = models.BooleanField(
        default=False, verbose_name="Utiliser la gestion des comptes bancaires"
    )

    class Meta:
        verbose_name = "Configuration ERP"
        verbose_name_plural = "Configuration ERP"

    @classmethod
    def get_config(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance