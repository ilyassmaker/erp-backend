from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from django.http import HttpResponse, FileResponse
from django.shortcuts import render
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import io
from django.utils.timezone import localdate   # ✅ ajoute ceci
from rest_framework.decorators import api_view
from .ml.prediction import predire_vente_mois_prochain
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime
from .utils import predire_risque_facture
import matplotlib
matplotlib.use('Agg') 

from rest_framework.response import Response
from rest_framework import status
from django.utils.timezone import now
from .models import (
    Person, Produit, Achat, LigneAchat, Commande, LigneCommande, Facture,
    Paiement, CompteBancaire, TransactionTresorerie, RelancePaiement,VenteHistorique
)
from .serializers import (
    PersonSerializer, ProduitSerializer, AchatSerializer, LigneAchatSerializer,
    CommandeSerializer, LigneCommandeSerializer, FactureSerializer,
    PaiementSerializer, CompteBancaireSerializer, TransactionTresorerieSerializer, RelancePaiementSerializer
)


# 🌿 ViewSets normaux
class PersonViewSet(viewsets.ModelViewSet):
    serializer_class = PersonSerializer

    def get_queryset(self):
        queryset = Person.objects.all()
        person_type = self.request.query_params.get('type', None)
        if person_type:
            queryset = queryset.filter(type=person_type)
        return queryset


class ProduitViewSet(viewsets.ModelViewSet):
    queryset = Produit.objects.all()
    serializer_class = ProduitSerializer


class AchatViewSet(viewsets.ModelViewSet):
    queryset = Achat.objects.all()
    serializer_class = AchatSerializer


class LigneAchatViewSet(viewsets.ModelViewSet):
    queryset = LigneAchat.objects.all()
    serializer_class = LigneAchatSerializer


class CommandeViewSet(viewsets.ModelViewSet):
    queryset = Commande.objects.all()
    serializer_class = CommandeSerializer


class LigneCommandeViewSet(viewsets.ModelViewSet):
    queryset = LigneCommande.objects.all()
    serializer_class = LigneCommandeSerializer


# 🌿 Facture ViewSet bloquant création/modification manuelle
class FactureViewSet(viewsets.ModelViewSet):
    queryset = Facture.objects.all()
    serializer_class = FactureSerializer

    def create(self, request, *args, **kwargs):
        raise ValidationError("La création manuelle de factures n'est pas autorisée.")

    def update(self, request, *args, **kwargs):
        raise ValidationError("La modification manuelle de factures n'est pas autorisée.")

    def partial_update(self, request, *args, **kwargs):
        raise ValidationError("La modification partielle de factures n'est pas autorisée.")


# 🌿 Génération de PDF

def download_facture_pdf(request, pk):
    try:
        facture = Facture.objects.get(pk=pk)
    except Facture.DoesNotExist:
        return HttpResponse("Facture non trouvée.", status=404)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 50
    y = height - margin

    try:
        # 🧩 En-tête titre centré
        p.setFont("Helvetica-Bold", 20)
        p.drawCentredString(width / 2, y, f"FACTURE N°{facture.id}")
        y -= 40

        # 🧾 Infos client ou fournisseur
        p.setFont("Helvetica", 12)
        if facture.commande:
            p.drawString(margin, y, f"Client : {facture.commande.client.nom}")
        elif facture.achat:
            p.drawString(margin, y, f"Fournisseur : {facture.achat.fournisseur.nom}")
        y -= 20
        p.drawString(margin, y, f"Date facture : {facture.date_facture.strftime('%d/%m/%Y')}")
        y -= 20
        p.drawString(margin, y, f"Statut facture : {facture.statut}")
        y -= 20
        # Montant payé et reste
        p.drawString(margin, y, f"Montant total     : {facture.montant_total:.2f} DH")
        y -= 15
        p.drawString(margin, y, f"Montant payé      : {facture.montant_paye:.2f} DH")
        y -= 15
        reste = facture.montant_total - facture.montant_paye
        p.drawString(margin, y, f"Reste à payer     : {reste:.2f} DH")
        y -= 15
        # Date d'échéance si présente
        if facture.date_echeance_restant:
            p.drawString(margin, y, f"Date d'échéance    : {facture.date_echeance_restant.strftime('%d/%m/%Y')}")
            y -= 20
        else:
            y -= 10

        # 🔹 Séparateur
        p.setStrokeColorRGB(0.6, 0.6, 0.6)
        p.setLineWidth(1)
        p.line(margin, y, width - margin, y)
        y -= 25

        # 🧾 En-tête des colonnes pour les lignes
        p.setFont("Helvetica-Bold", 12)
        p.drawString(margin, y, "Désignation")
        p.drawString(250, y, "Quantité")
        p.drawString(330, y, "Prix Unitaire")
        p.drawString(450, y, "Total ligne")
        y -= 20

        p.setFont("Helvetica", 10)
        lignes = facture.commande.lignecommande_set.all() if facture.commande else facture.achat.lignes.all()

        for ligne in lignes:
            if y < margin + 100:
                p.showPage()
                y = height - margin
                p.setFont("Helvetica-Bold", 12)
                p.drawString(margin, y, "Désignation")
                p.drawString(250, y, "Quantité")
                p.drawString(330, y, "Prix Unitaire")
                p.drawString(450, y, "Total ligne")
                y -= 20
                p.setFont("Helvetica", 10)

            total_ligne = (ligne.quantite or 0) * (ligne.prix_unitaire or 0)
            p.drawString(margin, y, ligne.produit.nom)
            p.drawString(250, y, str(ligne.quantite))
            p.drawString(330, y, f"{ligne.prix_unitaire:.2f} DH")
            p.drawString(450, y, f"{total_ligne:.2f} DH")
            y -= 18

        # 🔹 Séparateur avant section paiements
        y -= 10
        p.setLineWidth(0.5)
        p.line(margin, y, width - margin, y)
        y -= 25

        # 🧾 Section paiements passés
        p.setFont("Helvetica-Bold", 12)
        p.drawString(margin, y, "Historique des paiements :")
        y -= 18
        p.setFont("Helvetica", 10)

        paiements = facture.paiement_set.order_by('date_paiement')
        if paiements.exists():
            p.drawString(margin, y, "Date       Montant   Méthode      Référence")
            y -= 15
            for pay in paiements:
                if y < margin + 50:
                    p.showPage()
                    y = height - margin
                    p.setFont("Helvetica-Bold", 12)
                    p.drawString(margin, y, "Historique des paiements :")
                    y -= 18
                    p.setFont("Helvetica", 10)
                    p.drawString(margin, y, "Date       Montant   Méthode      Référence")
                    y -= 15

                p.drawString(margin, y, pay.date_paiement.strftime('%d/%m/%Y'))
                p.drawString(100, y, f"{pay.montant:.2f} DH")
                p.drawString(180, y, f"{pay.methode}")
                p.drawString(270, y, pay.reference_paiement)
                y -= 15
        else:
            p.drawString(margin, y, "Aucun paiement enregistré.")
            y -= 15

        # 🔹 Séparateur avant section relances
        y -= 10
        p.setLineWidth(0.5)
        p.line(margin, y, width - margin, y)
        y -= 25

        # 🧾 Section relances
        p.setFont("Helvetica-Bold", 12)
        p.drawString(margin, y, "Historique des relances :")
        y -= 18
        p.setFont("Helvetica", 10)

        relances = facture.relances.order_by('numero')
        if relances.exists():
            p.drawString(margin, y, "N°  Date       Statut   Note")
            y -= 15
            for rel in relances:
                if y < margin + 50:
                    p.showPage()
                    y = height - margin
                    p.setFont("Helvetica-Bold", 12)
                    p.drawString(margin, y, "Historique des relances :")
                    y -= 18
                    p.setFont("Helvetica", 10)
                    p.drawString(margin, y, "N°  Date       Statut   Note")
                    y -= 15

                p.drawString(margin, y, str(rel.numero))
                p.drawString(30, y, rel.date_relance.strftime('%d/%m/%Y'))
                p.drawString(100, y, rel.statut)
                p.drawString(160, y, rel.note)
                y -= 15
        else:
            p.drawString(margin, y, "Aucune relance.")
            y -= 15

        # 🔹 Ligne de séparation finale
        y -= 20
        p.setLineWidth(0.5)
        p.line(margin, y, width - margin, y)
        y -= 20

        # Footer signature
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(margin, y, "Merci pour votre confiance.")
        y -= 15
        p.drawString(margin, y, "Facture générée automatiquement par le système.")

        # Génération finale
        p.showPage()
        p.save()
        buffer.seek(0)

        return FileResponse(buffer, as_attachment=True, filename=f"facture_{pk}.pdf")

    except Exception as e:
        return HttpResponse(f"Erreur génération PDF : {str(e)}", status=500)


# 🌿 Autres ViewSets

class PaiementViewSet(viewsets.ModelViewSet):
    """
    - Gère la création des paiements (partiels ou complets).
    - Génère automatiquement une référence unique par jour : PAI-YYYYMMDD-NNNN
    - Met à jour la date d'échéance restante de la facture pour les paiements partiels.
    """
    queryset         = Paiement.objects.all().select_related('facture')
    serializer_class = PaiementSerializer

    def create(self, request, *args, **kwargs):
        data = request.data.copy()

        # ---------------- Vérifications préliminaires ---------------- #
        type_ref = data.get('type_reference')   # 'commande' ou 'achat'
        id_ref   = data.get('id_reference')

        if not type_ref or not id_ref:
            raise ValidationError(
                "Les champs 'type_reference' (commande/achat) et 'id_reference' sont requis."
            )

        # ---------------- Recherche de la facture liée ---------------- #
        facture = None
        if type_ref == "commande":
            facture = Facture.objects.filter(commande_id=id_ref).first()
        elif type_ref == "achat":
            facture = Facture.objects.filter(achat_id=id_ref).first()

        if not facture:
            raise ValidationError(f"Aucune facture trouvée pour {type_ref} id={id_ref}.")

        data["facture"] = facture.pk

        # ---------------- Génération de la référence paiement ---------- #
        if not data.get("reference_paiement"):
            today = localdate()  # ex. 2025-06-06
            seq   = (
                Paiement.objects.filter(date_paiement=today)
                                .count() + 1
            )
            data["reference_paiement"] = f"PAI-{today:%Y%m%d}-{seq:04d}"

        # ---------------- Sérialisation & sauvegarde ------------------- #
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        paiement = serializer.save()   # montant_paye mis à jour via signal ou surchargé en modèle

        # ---------------- Gestion date échéance (paiement partiel) ----- #
        paiement_complet = bool(data.get("paiement_complet", True))
        date_echeance_solde = data.get("date_echeance_solde")

        if not paiement_complet and date_echeance_solde:
            facture.date_echeance_restant = date_echeance_solde
            facture.save(update_fields=["date_echeance_restant"])

        return Response(
            self.get_serializer(paiement).data,
            status=status.HTTP_201_CREATED
        )


class CompteBancaireViewSet(viewsets.ModelViewSet):
    queryset = CompteBancaire.objects.all()
    serializer_class = CompteBancaireSerializer


class TransactionTresorerieViewSet(viewsets.ModelViewSet):
    queryset = TransactionTresorerie.objects.all()
    serializer_class = TransactionTresorerieSerializer


class RelancePaiementViewSet(viewsets.ModelViewSet):
    queryset = RelancePaiement.objects.all()
    serializer_class = RelancePaiementSerializer


# 🌿 Home
def home(request):
    return render(request, 'home.html')



@api_view(['GET'])
def predict_ventes(request, produit_id):
    prediction = predire_vente_mois_prochain(produit_id)
    return Response({"prediction": prediction})


@api_view(['GET'])
def historique_ventes(request, produit_id):
    ventes = (
        VenteHistorique.objects
        .filter(produit_id=produit_id)
        .order_by('mois')
        .values_list('mois', 'quantite')
    )
    # Formatage en liste JSON
    data = [
        {"mois": mois.strftime('%Y-%m'), "quantite": quantite}
        for mois, quantite in ventes
    ]
    return Response(data)


def ventes_prediction_plot(request):
    # 1. Charger les données
    ventes = VenteHistorique.objects.all().order_by('mois')
    if not ventes.exists():
        return HttpResponse("Pas de données", status=404)

    mois = np.array([v.mois.month for v in ventes]).reshape(-1, 1)
    quantites = np.array([v.quantite for v in ventes])

    # 2. Modèle linéaire simple
    model = LinearRegression()
    model.fit(mois, quantites)

    future_months = np.array([[mois[-1][0] + 1]])
    prediction = model.predict(future_months)

    # 3. Graphe matplotlib
    plt.figure(figsize=(8, 4))
    plt.scatter(mois, quantites, color='blue', label='Historique')
    plt.plot(mois, model.predict(mois), color='orange', label='Régression')
    plt.scatter(future_months, prediction, color='green', label='Prévision')
    plt.xlabel("Mois")
    plt.ylabel("Quantité vendue")
    plt.title("Prévision des ventes")
    plt.legend()
    plt.tight_layout()

    # 4. Sauvegarde dans un buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)

    return HttpResponse(buffer.getvalue(), content_type='image/png')


def predict_plot(request, produit_id):
    try:
        historique = VenteHistorique.objects.filter(produit_id=produit_id).order_by('mois')
        if not historique.exists():
            return HttpResponse("Pas de données", status=404)

        X = np.array(range(len(historique))).reshape(-1, 1)
        y = np.array([h.quantite for h in historique])

        model = LinearRegression().fit(X, y)
        y_pred = model.predict(X)

        # Prévision mois suivant
        next_month = model.predict([[len(X)]])

        # Graph
        plt.figure(figsize=(8, 4))
        plt.plot(X, y, 'bo-', label='Ventes réelles')
        plt.plot(X, y_pred, 'r--', label='Régression')
        plt.plot(len(X), next_month, 'go', label='Prévision')
        plt.title(f"Prévision des ventes - Produit ID {produit_id}")
        plt.xlabel("Mois (index)")
        plt.ylabel("Quantité vendue")
        plt.legend()
        plt.grid(True)

        # Génère l'image dans un buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)

        return HttpResponse(buf.getvalue(), content_type='image/png')

    except Exception as e:
        return HttpResponse(f"Erreur: {str(e)}", status=500)


@api_view(['GET'])
def api_predire_risque(request, client_id):
    res = predire_risque_facture(client_id)
    return Response({
        'risque_label': res['label'],
        'niveau': res['niveau']
    })
