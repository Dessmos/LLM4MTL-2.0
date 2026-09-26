"""Hard-coded runtime tool versions must match the engine harness poms.

ATL, QVT-O and Reactions write their tool versions into run provenance from
constants. These tests read the frozen harness ``pom.xml`` files (read-only)
so a version bump in a pom cannot leave the provenance silently wrong.
"""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from llm4mtl.languages import language_adapter
from llm4mtl.paths import TARGET

POM_NAMESPACE = {"m": "http://maven.apache.org/POM/4.0.0"}


def _pom(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def _dependency_version(pom: ET.Element, artifact_id: str) -> str | None:
    for dependency in pom.iterfind(".//m:dependency", POM_NAMESPACE):
        if dependency.findtext("m:artifactId", namespaces=POM_NAMESPACE) == artifact_id:
            return dependency.findtext("m:version", namespaces=POM_NAMESPACE)
    return None


def _property(pom: ET.Element, name: str) -> str | None:
    return pom.findtext(f"m:properties/m:{name}", namespaces=POM_NAMESPACE)


class RuntimeToolVersionTests(unittest.TestCase):

    def test_atl_versions_match_the_harness_pom(self) -> None:
        pom = _pom(TARGET.engine_harness("atl") / "pom.xml")
        expected = {
            "atl": _dependency_version(pom, "org.eclipse.m2m.atl.engine.emfvm"),
            "junit": _dependency_version(pom, "junit-jupiter"),
        }

        self.assertEqual(expected, language_adapter("atl").runtime_tool_versions())

    def test_qvto_versions_match_the_harness_pom(self) -> None:
        pom = _pom(TARGET.engine_harness("qvto") / "qvto-tests" / "pom.xml")
        expected = {
            "qvto-harness": pom.findtext("m:version", namespaces=POM_NAMESPACE),
            "junit": _property(pom, "junit.version"),
        }

        self.assertEqual(expected, language_adapter("qvto").runtime_tool_versions())

    def test_reactions_versions_match_the_harness_pom(self) -> None:
        pom = _pom(TARGET.engine_harness("reactions") / "pom.xml")
        expected = {
            "vitruv": _property(pom, "vitruv.version"),
            "junit": _dependency_version(pom, "junit-jupiter-api"),
        }

        self.assertEqual(
            expected, language_adapter("reactions").runtime_tool_versions()
        )


if __name__ == "__main__":
    unittest.main()
