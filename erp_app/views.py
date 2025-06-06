# erp_app/views.py

from django.http           import HttpResponse, FileResponse
from django.shortcuts      import render
from django.utils.timezone import now
from reportlab.pdfgen      import canvas
from reportlab.lib.pagesizes import A4
import io

from rest_framework import viewsets, status
from rest_framework.response   import Response
from rest_framework.exceptions import ValidationError

from .models import (
    Person, Produit, Achat, LigneAchat, Commande, LigneCommande,
    Facture, Paiement, CompteBancaire, TransactionTresorerie, RelancePaiement
)
from .serializers import (
    PersonSerializer, ProduitSerializer, AchatSerializer, LigneAchatSerializer,
    CommandeSerializer, LigneCommandeSerializer, FactureSerializer,
    PaiementSerializer, CompteBancaireSerializer,
    TransactionTresorerieSerializer, RelancePaiementSerializer
)


# ────────────────────────────────────────────────────────────────────────────────
# 1. ViewSets « simples »
# ────────────────────────────────────────────────────────────────────────────────

class PersonViewSet(viewsets.ModelViewSet):
    serializer_class = PersonSerializer

    def get_queryset(self):
        queryset    = Person.objects.all()
        person_type = self.request.query_params.get('type', None)
        if person_type:
            queryset = queryset.filter(type=person_type)
        return queryset


class ProduitViewSet(viewsets.ModelViewSet):
    queryset         = Produit.objects.all()
    serializer_class = ProduitSerializer


class AchatViewSet(viewsets.ModelViewSet):
    queryset         = Achat.objects.all()
    serializer_class = AchatSerializer


class LigneAchatViewSet(viewsets.ModelViewSet):
    queryset         = LigneAchat.objects.all()
    serializer_class = LigneAchatSerializer


class CommandeViewSet(viewsets.ModelViewSet):
    queryset         = Commande.objects.all()
    serializer_class = CommandeSerializer


class LigneCommandeViewSet(viewsets.ModelViewSet):
    queryset         = LigneCommande.objects.all()
    serializer_class = LigneCommandeSerializer


# ────────────────────────────────────────────────────────────────────────────────
# 2. Facture : CRUD désactivé côté API
# ────────────────────────────────────────────────────────────────────────────────

class FactureViewSet(viewsets.ModelViewSet):
    queryset         = Facture.objects.all()
    serializer_class = FactureSerializer

    def create(self, request, *args, **kwargs):
        raise ValidationError("La création manuelle de factures n'est pas autorisée.")

    def update(self, request, *args, **kwargs):
        raise ValidationError("La modification manuelle de factures n'est pas autorisée.")

    def partial_update(self, request, *args, **kwargs):
        raise ValidationError("La modification partielle de factures n'est pas autorisée.")


# ────────────────────────────────────────────────────────────────────────────────
# 3. Génération de PDF pour une facture existante
# ────────────────────────────────────────────────────────────────────────────────

def download_facture_pdf(request, pk):
    try:
        facture = Facture.objects.get(pk=pk)
    except Facture.DoesNotExist:
        return HttpResponse("Facture non trouvée.", status=404)

    buffer = io.BytesIO()
    p      = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 50
    y      = height - margin

    try:
        # En-tête centré
        p.setFont("Helvetica-Bold", 20)
        p.drawCentredString(width / 2, y, f"FACTURE N°{facture.id}")
        y -= 40

        # Infos client ou fournisseur
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

        # Montant total, payé, reste
        p.drawString(margin, y, f"Montant total     : {facture.montant_total:.2f} DH")
        y -= 15
        p.drawString(margin, y, f"Montant payé      : {facture.montant_paye:.2f} DH")
        y -= 15
        reste = facture.montant_total - facture.montant_paye
        p.drawString(margin, y, f"Reste à payer     : {reste:.2f} DH")
        y -= 15

        # Date d'échéance si partiel
        if facture.date_echeance_restant:
            p.drawString(margin, y, f"Date d'échéance    : {facture.date_echeance_restant.strftime('%d/%m/%Y')}")
            y -= 20
        else:
            y -= 10

        # Séparateur
        p.setStrokeColorRGB(0.6, 0.6, 0.6)
        p.setLineWidth(1)
        p.line(margin, y, width - margin, y)
        y -= 25

        # En-tête colonnes lignes
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

        # Séparateur avant paiements
        y -= 10
        p.setLineWidth(0.5)
        p.line(margin, y, width - margin, y)
        y -= 25

        # Section paiements
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

        # Séparateur avant relances
        y -= 10
        p.setLineWidth(0.5)
        p.line(margin, y, width - margin, y)
        y -= 25

        # Section relances
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

        # Ligne de séparation finale
        y -= 20
        p.setLineWidth(0.5)
        p.line(margin, y, width - margin, y)
        y -= 20

        # Footer
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(margin, y, "Merci pour votre confiance.")
        y -= 15
        p.drawString(margin, y, "Facture générée automatiquement par le système.")

        p.showPage()
        p.save()
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename=f"facture_{pk}.pdf")

    except Exception as e:
        return HttpResponse(f"Erreur génération PDF : {str(e)}", status=500)


# ────────────────────────────────────────────────────────────────────────────────
# 4. PaiementViewSet : gestion complet / partiel + référence auto
# ────────────────────────────────────────────────────────────────────────────────
class PaiementViewSet(viewsets.ModelViewSet):
    queryset         = Paiement.objects.all()
    serializer_class = PaiementSerializer

    def create(self, request, *args, **kwargs):
        data = request.data.copy()

        type_ref = data.get('type_reference')
        id_ref   = data.get('id_reference')
        if not type_ref or not id_ref:
            return Response({"detail": "type_reference et id_reference requis."},
                            status=status.HTTP_400_BAD_REQUEST)

        facture = (Facture.objects.filter(commande__id=id_ref).first()
                   if type_ref == 'commande'
                   else Facture.objects.filter(achat__id=id_ref).first())
        if not facture:
            return Response({"detail": "Facture introuvable."}, status=status.HTTP_404_NOT_FOUND)

        data['facture'] = facture.id

        if not data.get('reference_paiement'):
            today  = now().strftime("%Y%m%d")
            count  = Paiement.objects.filter(date_paiement=now().date()).count() + 1
            data['reference_paiement'] = f"PAI-{today}-{count:03d}"

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        paiement = serializer.save()          # ← déclenche la logique du modèle

        return Response(self.get_serializer(paiement).data, status=status.HTTP_201_CREATED)


# ────────────────────────────────────────────────────────────────────────────────
# 5. ViewSets complémentaires
# ────────────────────────────────────────────────────────────────────────────────

class CompteBancaireViewSet(viewsets.ModelViewSet):
    queryset         = CompteBancaire.objects.all()
    serializer_class = CompteBancaireSerializer


class TransactionTresorerieViewSet(viewsets.ModelViewSet):
    queryset         = TransactionTresorerie.objects.all()
    serializer_class = TransactionTresorerieSerializer


class RelancePaiementViewSet(viewsets.ModelViewSet):
    queryset         = RelancePaiement.objects.all()
    serializer_class = RelancePaiementSerializer


# ────────────────────────────────────────────────────────────────────────────────
# 6. Accueil simple
# ────────────────────────────────────────────────────────────────────────────────

def home(request):
    return render(request, 'home.html')
