"""
AFIP/ARCA electronic invoicing service.
Flow: sign LoginTicketRequest with cert/key → WSAA → get token+sign → WSFE FECAESolicitar → get CAE
"""
import base64
import re
from datetime import datetime, timedelta, timezone
from typing import Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization.pkcs7 import (
    PKCS7Options,
    PKCS7SignatureBuilder,
)
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from zeep import Client as SoapClient
from zeep.transports import Transport
import requests

WSAA_TESTING = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
WSAA_PROD = "https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL"
WSFE_TESTING = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
WSFE_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"


def _build_tra(service: str = "wsfe") -> bytes:
    now = datetime.now(timezone.utc)
    gen = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    exp = (now + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    unique_id = int(now.timestamp())
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <destination>cn=wsaa,o=afip,c=ar,serialNumber=CUIT 33693450239</destination>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{gen}</generationTime>
    <expirationTime>{exp}</expirationTime>
  </header>
  <service>{service}</service>
</loginTicketRequest>"""
    return xml.encode("utf-8")


def _sign_tra(tra_bytes: bytes, cert_pem: str, key_pem: str) -> str:
    cert = load_pem_x509_certificate(cert_pem.encode())
    key = load_pem_private_key(key_pem.encode(), password=None)
    signed = (
        PKCS7SignatureBuilder()
        .set_data(tra_bytes)
        .add_signer(cert, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [PKCS7Options.DetachedSignature])
    )
    return base64.b64encode(signed).decode()


def get_wsaa_token(cert_pem: str, key_pem: str, production: bool = False) -> Tuple[str, str]:
    """Returns (token, sign) from WSAA."""
    tra = _build_tra("wsfe")
    cms_b64 = _sign_tra(tra, cert_pem, key_pem)
    wsdl = WSAA_PROD if production else WSAA_TESTING
    session = requests.Session()
    session.verify = True
    transport = Transport(session=session)
    client = SoapClient(wsdl, transport=transport)
    response = client.service.loginCms(in0=cms_b64)
    token = re.search(r"<token>(.*?)</token>", response, re.DOTALL).group(1)
    sign = re.search(r"<sign>(.*?)</sign>", response, re.DOTALL).group(1)
    return token, sign


def emit_cae(
    cuit: str,
    punto_venta: int,
    cbte_tipo: int,
    concepto: int,
    doc_tipo: int,
    doc_nro: str,
    importe_total: float,
    fecha: str,
    cert_pem: str,
    key_pem: str,
    production: bool = False,
) -> dict:
    """
    Calls WSFE FECAESolicitar.
    Returns {"cae": "...", "cae_fch_vto": "YYYYMMDD", "cbte_nro": N}.
    Raises ValueError on AFIP error.
    """
    token, sign = get_wsaa_token(cert_pem, key_pem, production)
    wsdl = WSFE_PROD if production else WSFE_TESTING
    session = requests.Session()
    transport = Transport(session=session)
    client = SoapClient(wsdl, transport=transport)

    auth = {"Token": token, "Sign": sign, "Cuit": cuit}

    last = client.service.FECompUltimoAutorizado(Auth=auth, PtoVta=punto_venta, CbteTipo=cbte_tipo)
    if hasattr(last, "Errors") and last.Errors:
        raise ValueError(f"AFIP FECompUltimoAutorizado error: {last.Errors.Err[0].Msg}")
    next_cbte = (last.CbteNro or 0) + 1

    req = {
        "FeCabReq": {
            "CantReg": 1,
            "PtoVta": punto_venta,
            "CbteTipo": cbte_tipo,
        },
        "FeDetReq": {
            "FECAEDetRequest": [
                {
                    "Concepto": concepto,
                    "DocTipo": doc_tipo,
                    "DocNro": doc_nro,
                    "CbteDesde": next_cbte,
                    "CbteHasta": next_cbte,
                    "CbteFch": fecha,
                    "ImpTotal": round(importe_total, 2),
                    "ImpTotConc": 0,
                    "ImpNeto": round(importe_total, 2),
                    "ImpOpEx": 0,
                    "ImpIVA": 0,
                    "ImpTrib": 0,
                    "MonId": "PES",
                    "MonCotiz": 1,
                }
            ]
        },
    }
    result = client.service.FECAESolicitar(Auth=auth, FeCAEReq=req)
    if hasattr(result, "Errors") and result.Errors:
        raise ValueError(f"AFIP error: {result.Errors.Err[0].Msg}")
    det = result.FeDetResp.FECAEDetResponse[0]
    if det.Resultado != "A":
        obs = ""
        if hasattr(det, "Observaciones") and det.Observaciones:
            obs = det.Observaciones.Obs[0].Msg
        raise ValueError(f"AFIP rechazó el comprobante: {obs}")
    return {
        "cae": det.CAE,
        "cae_fch_vto": det.CAEFchVto,
        "cbte_nro": next_cbte,
    }
