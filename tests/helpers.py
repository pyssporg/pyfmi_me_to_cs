"""Shared test helper utilities."""
from __future__ import annotations

import zipfile

from pyssp_standard.standard.ssp1.codec.ssd_codec import Ssp1SsdCodec
from pyssp_standard.standard.ssp1.model.ssc_model import Ssp1Annotation
from pyssp_standard.standard.ssp1.model.ssd_model import (
    Ssd1Component,
    Ssd1Connection,
    Ssd1Connector,
    Ssd1ParameterBinding,
    Ssd1System,
    Ssd1SystemStructureDescription,
)
from pyssp_standard.standard.ssp1.model.ssv_model import Ssp1ParameterSet


def make_test_fmu(path: str, model_description_xml: str) -> None:
    """Write a minimal FMU ZIP containing *model_description_xml* to *path*."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modelDescription.xml", model_description_xml)


def build_ssp_document(
    *,
    fmu_sources: dict[str, str],
    connectors: list[dict] | None = None,
    connections: list[tuple[str, str, str, str]] | None = None,
    parameters: list[tuple[str, str, object]] | None = None,
    annotations: list[tuple[str, object]] | None = None,
    name: str = "system",
) -> Ssd1SystemStructureDescription:
    """Build an ``Ssd1SystemStructureDescription`` for testing.

    ``fmu_sources`` maps a component name to its ``source`` URI.
    ``connectors`` entries are dicts with ``element``/``name``/``kind``/
    optional ``type_name`` keys.  ``connections`` are
    ``(start_element, start_connector, end_element, end_connector)`` tuples.
    ``parameters`` are ``(name, type_name, value)`` triples stored in an
    inline parameter binding.
    """
    doc = Ssd1SystemStructureDescription(name=name, version="1.0")
    system = Ssd1System(name="System")
    system.elements = [
        Ssd1Component(name=cname, source=source)
        for cname, source in fmu_sources.items()
    ]
    for connector in connectors or []:
        system.connectors.append(
            Ssd1Connector(
                element=connector["element"],
                name=connector["name"],
                kind=connector["kind"],
                type_name=connector.get("type_name"),
            )
        )
    for start_element, start_connector, end_element, end_connector in connections or []:
        system.connections.append(
            Ssd1Connection(
                start_element=start_element,
                start_connector=start_connector,
                end_element=end_element,
                end_connector=end_connector,
            )
        )
    if parameters:
        parameter_set = Ssp1ParameterSet(name="parameters", version="1.0")
        for parname, ptype, value in parameters:
            parameter_set.add_parameter(parname, ptype or "Real", value=value)
        system.parameter_bindings.append(
            Ssd1ParameterBinding(parameter_set=parameter_set)
        )
    doc.system = system
    for annotation_type, elements in annotations or []:
        doc.metadata.annotations.append(
            Ssp1Annotation(type_name=annotation_type, elements=list(elements))
        )
    return doc


def make_fmu_bytes(model_identifier: str = "model") -> bytes:
    """Return bytes of a minimal FMI 2.0 ME FMU archive."""
    xml = (
        f'<fmiModelDescription fmiVersion="2.0" modelName="{model_identifier}" '
        f'guid="{{test-guid}}"><ModelExchange modelIdentifier="{model_identifier}"/>'
        f"<ModelVariables/></fmiModelDescription>"
    )
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modelDescription.xml", xml)
    return buf.getvalue()