import abc
import datetime


class PaymentProvider(abc.ABC):
    id = "base"

    @abc.abstractmethod
    def create_invoice(self, invoice):
        raise NotImplementedError

    @abc.abstractmethod
    def get_invoice_status(self, invoice):
        raise NotImplementedError

    @abc.abstractmethod
    def cancel_invoice(self, invoice):
        raise NotImplementedError

    @abc.abstractmethod
    def handle_webhook(self, payload):
        raise NotImplementedError


class ManualPaymentProvider(PaymentProvider):
    id = "manual"

    def create_invoice(self, invoice):
        invoice.provider = self.id
        invoice.provider_invoice_id = invoice.invoice_number
        invoice.status = "pending_payment"
        invoice.payment_url = (
            f"/plugins/platform-plus/payments/invoices/{invoice.id}/pay"
            if invoice.id
            else None
        )
        return invoice

    def get_invoice_status(self, invoice):
        return invoice.status

    def cancel_invoice(self, invoice):
        invoice.status = "cancelled"
        return invoice

    def handle_webhook(self, payload):
        return {
            "provider": self.id,
            "event_type": "manual.webhook_ignored",
            "status": "ignored",
            "received_at": datetime.datetime.utcnow().isoformat(),
        }


def get_payment_provider(provider_id=None):
    provider_id = provider_id or "manual"
    providers = {
        ManualPaymentProvider.id: ManualPaymentProvider,
    }
    return providers.get(provider_id, ManualPaymentProvider)()
