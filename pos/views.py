# pos/views.py
from decimal import Decimal
from django.db import transaction
from django.utils.dateparse import parse_date
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from rest_framework.decorators import action


from restaurants.permissions import IsRestaurateur, IsAdminVegNBio
from .models import Order, OrderItem, Payment
from .serializers import OrderSerializer, OrderItemSerializer, PaymentSerializer

import io
from decimal import Decimal, ROUND_HALF_UP
from django.http import HttpResponse
from django.utils import timezone

# ReportLab
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

def _is_owner(user, order: Order) -> bool:
    return getattr(user, "role", None) in ["RESTAURATEUR","ADMIN"] and (
        order.restaurant.owner == user or getattr(user, "role", None) == "ADMIN"
    )

def _q2(x: Decimal) -> Decimal:
    """Arrondi financier 2 décimales."""
    return (Decimal(x or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def _eur(x: Decimal) -> str:
    return f"{_q2(x):.2f} €"

def _method_label(m: str) -> str:
    return {"CASH": "Espèces", "CARD": "Carte", "ONLINE": "En ligne"}.get((m or "").upper(), m or "—")

def _compute_net(order) -> dict:
    """
    Recalcule HT / remises pour l'affichage (en miroir de recalc_totals()).
    """
    subtotal = _q2(order.subtotal)
    discount = _q2(order.discount_amount)
    if order.discount_percent and order.discount_percent > 0:
        discount += _q2(subtotal * order.discount_percent / Decimal("100"))
    net = subtotal - discount
    if net < 0: net = Decimal("0.00")
    tax_total = _q2(net * order.tax_rate / Decimal("100"))
    total_ttc = _q2(net + tax_total)
    return {
        "subtotal": subtotal,
        "discount": discount,
        "net": net,
        "tax_total": tax_total,
        "total_ttc": total_ttc,
    }

def _estimate_page_height(items_count: int) -> float:
    """
    Hauteur de page approximative (pour un ticket 80 mm de large).
    Évite une 2e page tant que possible.
    """
    base = 160  # mm (entête + totaux)
    per_line = 6  # mm par item
    h = max(180, base + items_count * per_line)
    return h * mm

def build_ticket_pdf_80mm(order) -> bytes:
    """
    Ticket “80 mm” façon caisse : entête, lignes, totaux, TVA, paiements, rendu.
    """
    # --- Contexte & calculs ---
    rest = order.restaurant
    lines = list(order.items.all())
    calc = _compute_net(order)
    articles_count = sum((it.quantity for it in lines), 0)

    # --- Mise en page ---
    W = 80 * mm
    H = _estimate_page_height(len(lines))  # hauteur dynamique
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=(W, H),
        leftMargin=6 * mm, rightMargin=6 * mm,
        topMargin=8 * mm, bottomMargin=8 * mm,
        title=f"ticket-{order.id}"
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=14, leading=16, alignment=1)
    H2 = ParagraphStyle("H2", parent=styles["Heading3"], fontSize=10, leading=12, alignment=1)
    N  = ParagraphStyle("N",  parent=styles["Normal"],  fontSize=9,  leading=11)
    S  = ParagraphStyle("S",  parent=styles["Normal"],  fontSize=8,  leading=10, textColor=colors.grey)

    story = []

    # --- Header (logo texte + raison sociale/coordonnées) ---
    story.append(Paragraph("Veg’N Bio", H1))
    addr = f"{rest.name}<br/>{rest.address}<br/>{rest.postal_code} {rest.city}"
    story.append(Paragraph(addr, H2))
    story.append(Spacer(1, 4))

    # --- Métadonnées ---
    opened = timezone.localtime(order.opened_at).strftime("%d/%m/%Y %H:%M")
    closed = order.closed_at and timezone.localtime(order.closed_at).strftime("%d/%m/%Y %H:%M")
    cashier = getattr(order.cashier, "email", None) or getattr(order.cashier, "username", "—")

    meta_lines = [
        f"Ticket&nbsp;#: <b>{order.id}</b>",
        f"Date&nbsp;: {opened}",
        f"Caisse&nbsp;: {cashier}",
    ]
    if closed:
        meta_lines.append(f"Fermée&nbsp;: {closed}")
    story.append(Paragraph("<br/>".join(meta_lines), N))
    story.append(Spacer(1, 4))

    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black))
    story.append(Spacer(1, 4))

    # --- Tableau des lignes ---
    data = [["Article", "PU", "Qté", "Total"]]
    for it in lines:
        label = it.custom_name or (it.dish.name if it.dish else "Article")
        total = _q2(it.unit_price * it.quantity)
        data.append([
            Paragraph(label, N),
            _eur(it.unit_price),
            str(it.quantity),
            _eur(total),
        ])

    tbl = Table(
        data,
        colWidths=[None, 20*mm, 12*mm, 22*mm],
        hAlign="LEFT",
    )
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 9),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("ALIGN", (0,1), (0,-1), "LEFT"),
        ("LINEBELOW", (0,0), (-1,0), 0.7, colors.black),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
        ("INNERGRID", (0,0), (-1,-1), 0.2, colors.lightgrey),
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6))

    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    story.append(Spacer(1, 4))

    # --- Bloc "Total à payer (n articles)" ---
    titre_total = f"Total à payer  ({articles_count} article{'s' if articles_count>1 else ''})"
    t_total = Table([[Paragraph(titre_total, N), Paragraph(_eur(calc['total_ttc']), ParagraphStyle('R', parent=N, alignment=2))]],
                    colWidths=[None, 26*mm])
    t_total.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,0), "Helvetica-Bold"),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
    ]))
    story.append(t_total)
    story.append(Spacer(1, 2))

    # --- Détail HT/TVA/TTC ---
    taux = f"{_q2(order.tax_rate):.2f} %"
    detail = [
        ["Total HT", _eur(calc["net"])],
        [f"TVA ({taux})", _eur(calc["tax_total"])],
        ["Total TTC", _eur(calc["total_ttc"])],
    ]
    t_detail = Table(detail, colWidths=[None, 26*mm], hAlign="RIGHT")
    t_detail.setStyle(TableStyle([
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("LINEABOVE", (0,2), (-1,2), 0.5, colors.black),
        ("FONTNAME", (0,2), (-1,2), "Helvetica-Bold"),
    ]))
    story.append(t_detail)

    # --- Remises (afficher uniquement si ≠ 0) ---
    if calc["discount"] > 0:
        rem = f"Remise"
        if order.discount_percent and order.discount_percent > 0:
            rem += f" ({_q2(order.discount_percent):.2f} %)"
        t_rem = Table([[rem, f"- {_eur(calc['discount'])}"]], colWidths=[None, 26*mm], hAlign="RIGHT")
        t_rem.setStyle(TableStyle([
            ("ALIGN", (1,0), (1,0), "RIGHT"),
            ("TEXTCOLOR", (0,0), (-1,0), colors.darkred),
        ]))
        story.append(Spacer(1, 2))
        story.append(t_rem)

    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    story.append(Spacer(1, 4))

    # --- Paiements & rendu ---
    pays = list(order.payments.all().order_by("received_at"))
    if pays:
        rows = []
        for p in pays:
            dt = timezone.localtime(p.received_at).strftime("%d/%m %H:%M")
            rows.append([f"{_method_label(p.method)} ({dt})", _eur(p.amount)])
        t_pay = Table(rows, colWidths=[None, 26*mm], hAlign="RIGHT")
        t_pay.setStyle(TableStyle([
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ]))
        story.append(t_pay)

    # Totaux encaissés + rendu
    t_paid = Table([
        ["Payé",  _eur(order.paid_amount)],
        ["Rendu", _eur(order.change_due)],
    ], colWidths=[None, 26*mm], hAlign="RIGHT")
    t_paid.setStyle(TableStyle([
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("LINEABOVE", (0,0), (-1,0), 0.5, colors.black),
    ]))
    story.append(Spacer(1, 4))
    story.append(t_paid)

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="70%", thickness=0.4, color=colors.grey))
    story.append(Spacer(1, 6))

    # --- Footer ---
    story.append(Paragraph("Merci pour votre visite 🌱", N))
    story.append(Paragraph("Veg’N Bio — Cuisine végétarienne & locale", S))

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()
    return pdf


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related("restaurant","cashier").prefetch_related("items","payments").all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        if self.action in [
            "create","update","partial_update","destroy",
            "add_item","update_item","remove_item",
            "apply_discount","hold","reopen","checkout","cancel",
            "ticket","summary"
        ]:
            Combined = IsRestaurateur | IsAdminVegNBio
            return [permissions.IsAuthenticated(), Combined()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        # filtre par restaurant/date
        p = self.request.query_params
        if p.get("restaurant"):
            qs = qs.filter(restaurant_id=p["restaurant"])
        if p.get("date"):
            d = parse_date(p["date"])
            if d:
                qs = qs.filter(opened_at__date=d)
        return qs

    def perform_create(self, serializer):
        order = serializer.save(cashier=self.request.user)
        order.recalc_totals()
        order.save(update_fields=["subtotal","tax_total","total_due","change_due"])

    def perform_update(self, serializer):
        order = self.get_object()
        if not _is_owner(self.request.user, order):
            return Response({"detail":"Accès interdit."}, status=403)
        order.ensure_mutable()
        order = serializer.save()
        order.recalc_totals()
        order.save(update_fields=["subtotal","tax_total","total_due","change_due"])

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        if not _is_owner(request.user, order):
            return Response({"detail":"Accès interdit."}, status=403)
        if order.status not in ["OPEN","HOLD"]:
            return Response({"detail":"Impossible de supprimer: commande non modifiable."}, status=400)
        return super().destroy(request, *args, **kwargs)

    # ------- Lignes -------
    @action(detail=True, methods=["post"])
    def add_item(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail": "Accès interdit."}, status=403)
        order.ensure_mutable()

        ser = OrderItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(order=order)

        # 🔧 rafraîchir l'instance avant recalc (pour être 100% sûr)
        order.refresh_from_db()

        order.recalc_totals()
        order.save(update_fields=["subtotal", "tax_total", "total_due", "change_due"])
        return Response(OrderSerializer(order).data, status=201)

    # update_item : PATCH / PUT sur .../items/<id>/update/
    @action(detail=True, methods=["patch", "put"], url_path=r"items/(?P<item_id>\d+)/update", url_name="update_item")
    def update_item(self, request, pk=None, item_id=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail": "Accès interdit."}, status=403)
        order.ensure_mutable()

        try:
            item = order.items.get(pk=item_id)
        except OrderItem.DoesNotExist:
            return Response({"detail": "Ligne introuvable."}, status=404)

        ser = OrderItemSerializer(item, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()

        order.refresh_from_db()  # 🔧
        order.recalc_totals()
        order.save(update_fields=["subtotal", "tax_total", "total_due", "change_due"])
        return Response(OrderSerializer(order).data)

    # remove_item : DELETE sur .../items/<id>/remove/
    @action(detail=True, methods=["delete"], url_path=r"items/(?P<item_id>\d+)/remove", url_name="remove_item")
    def remove_item(self, request, pk=None, item_id=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail": "Accès interdit."}, status=403)
        order.ensure_mutable()

        deleted, _ = order.items.filter(pk=item_id).delete()
        if not deleted:
            return Response({"detail": "Ligne introuvable."}, status=404)

        order.refresh_from_db()  # 🔧
        order.recalc_totals()
        order.save(update_fields=["subtotal", "tax_total", "total_due", "change_due"])
        return Response(OrderSerializer(order).data)


    # ------- Remise / statut -------
    @action(detail=True, methods=["post"])
    def apply_discount(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        order.ensure_mutable()
        amount = Decimal(str(request.data.get("discount_amount", "0") or "0"))
        percent = Decimal(str(request.data.get("discount_percent", "0") or "0"))
        if percent < 0 or percent > 100:
            return Response({"detail":"discount_percent doit être 0..100."}, status=400)
        order.discount_amount = amount
        order.discount_percent = percent
        order.recalc_totals(); order.save(update_fields=["discount_amount","discount_percent","subtotal","tax_total","total_due","change_due"])
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def hold(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        order.ensure_mutable()
        order.status = "HOLD"
        order.save(update_fields=["status"])
        return Response({"status":"HOLD"})

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        if order.status not in ["HOLD","CANCELLED"]:
            return Response({"detail":"Seules les commandes en HOLD/ANNULÉE peuvent être rouvertes."}, status=400)
        order.status = "OPEN"
        order.save(update_fields=["status"])
        return Response({"status":"OPEN"})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        if order.status in ["PAID","REFUNDED"]:
            return Response({"detail":"Commande payée: annulation impossible (faire un remboursement)."}, status=400)
        order.status = "CANCELLED"
        order.save(update_fields=["status"])
        return Response({"status":"CANCELLED"})

    # ------- Encaissement -------
    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        """
        Enregistre un paiement et clôt si total atteint.
        Body: { "method": "CASH|CARD|ONLINE", "amount": 25.00, "note": "..." }
        """
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        if order.status in ["CANCELLED","REFUNDED"]:
            return Response({"detail":"Commande annulée/remboursée."}, status=400)

        ser = PaymentSerializer(data={**request.data, "order": order.id})
        ser.is_valid(raise_exception=True)

        with transaction.atomic():
            payment = ser.save()
            order.paid_amount = (order.paid_amount + payment.amount).quantize(Decimal("0.01"))
            order.recalc_totals()
            order.close_if_paid()
            order.save(update_fields=["paid_amount","subtotal","tax_total","total_due","change_due","status","closed_at"])

        return Response({"status": order.status,
                         "paid_amount": str(order.paid_amount),
                         "change_due": str(order.change_due)})

    # ------- Ticket / Résumé -------
    @action(detail=True, methods=["get"], url_path=r"ticket\.pdf", url_name="ticket_pdf")
    def ticket_pdf(self, request, pk=None):
        """
        GET /api/pos/orders/{id}/ticket.pdf[?inline=1]
        Retourne le ticket de caisse PDF (format 80 mm).
        """
        order = self.get_object()
        if not _is_owner(request.user, order):
            return Response({"detail": "Accès interdit."}, status=403)

        pdf_bytes = build_ticket_pdf_80mm(order)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        disp = "inline" if request.GET.get("inline") in ["1", "true", "yes"] else "attachment"
        resp["Content-Disposition"] = f'{disp}; filename="ticket-{order.id}.pdf"'
        return resp

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        /api/pos/orders/summary/?restaurant=1&date=2025-10-10
        """
        qs = self.get_queryset()
        total = sum((o.total_due for o in qs if o.status in ["PAID","REFUNDED"]), Decimal("0.00"))
        count = qs.count()
        return Response({"count": count, "turnover": str(total)})
