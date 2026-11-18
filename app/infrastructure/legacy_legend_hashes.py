"""SHA-256 der früheren Standard-Legendentexte eingebauter Diagnosesymbole (aus der Git-Historie).

Erkennt bei der Migration einer Arbeitskopie (``symbol_catalog_migration``), ob
deren Legende unverändert ein früherer Standardtext ist – dann ersetzen die
Standard-Kompetenzen sie verlustfrei. Hashes statt Texte, damit die alten
Formulierungen nicht ein zweites Mal im Code stehen (SSOT bleibt
``default_competences.json``). Hash über die drei Stufentexte (Zeilenumbruch
als Trenner, je nach ``strip()``), s. :func:`legend_fingerprint`.
"""

from __future__ import annotations

import hashlib

LEGACY_LEGEND_SHA256: dict[str, frozenset[str]] = {
    "1F446": frozenset({
        "2217ad89cd8c492e520f884546cc17c17bda40e65b672c6ad55cda975bc9a792",
        "39c4251e24e7a55132f3bc80ee89146cd21c4d5b6cce7ac3046959ea27203015",
        "71f2750c827305a641ec649c9e3f18a1bc32ecee81561a2e37ebb82326e2bed0",
        "b356838195beb1f2be4645bc0cb92a262320a696007fcbde2f95678e69894439",
        "f414d0969a58bae80883244972ea806d87b0c724b3f2128c814b1b89edf94e4e",
    }),
    "221E": frozenset({
        "2af410ec6f53f9c1e83edc3a41e786061eb8c9a70bd6dda581c28fc81308e600",
        "2d97c21c8ed8efbfa766c9011205cf183c0f19ff64c099b3678ffa108a4cfca7",
        "965bde5886101c2a64bb148bfcd15453963f066fe99b73f2b854fd37d5acadc8",
        "a813a4e965e4e179a05cf016cf1d4056f4eddd8a20f60a9c8f6b8ee02c63115d",
    }),
    "1F5E9": frozenset({
        "16fa12940d49bcae606ecfe54b5d3a2c5a5e17c1ef3ee55a3a5b8bd3f05f7d67",
        "2a3f71f750bafccbda890a20c18736244a01ab30187b5d25efbae6f2e8a88af8",
        "8e0ab5066ad7d7bda70acd49e6118a49547e7637a8c54f61db7abf8b6aa6c83f",
        "e443bdc4f6bb400f07a2a753eed0c832c83e48132e543e63db6749c1911fe808",
        "f0997127243c40381c8057eccf0bc74f22044be03204f8539ca6268b1cde2c99",
    }),
    "1F5F2": frozenset({
        "80fada4157a3e106286705c55e8954a390384df878479672ab7e85872d3a93c8",
        "e6244a16b117d3e0e8d867f996585406bc7f256723c84b6bd54ae4519ab09c32",
        "f430362eb5ad797b4b25f75d9f8b62151ea6a94b878672e88739861386d432dd",
        "f6e4b62bf9d215e703f730d1c3ef56a189c1022dfd3a0c5ed97cb65626c203d4",
    }),
    "1F590": frozenset({
        "30df9bbaa78b67cc4fd0079b1aa7b43e66c7147bcca16b3a6e37da54e54952b1",
        "720e30c17e84c4851e97e031f7a690c712c7c3f16c4c13784813f32dc42a9752",
        "d8d70c568dee7f6b81884fa1ae866f0738705d70e89b77bc9fd3781eb7753aa0",
    }),
    "1F3AF": frozenset({
        "b29aef78ffe045e028053f7e3f429f134829a1a9bb60323eb0824e87c015b382",
    }),
    "1F5CE": frozenset({
        "2354e593b429970b5f344c4781dd5b6d7d6c1663ea192e20b8d67124cb7d1795",
        "80963366feb4552cb409653c59a4ae61c08419157423b9c505f2d14d47d98307",
        "9a9762596a63e125bf3b590ada861bc554f0b849c41b9d6313eb2599eddf7dc3",
        "9f3f34459bbe9cb798e67c29f79818623602885c77813867ba130e72f050d2ba",
    }),
    "264B": frozenset({
        "4d96f40b8fd1042fe81861e030e3a60a212874205a156b0874d80c766df7771c",
        "5372a1412ef06d3847b0213d54951f4a1ccb083c8d6bfcaca904aab72915fc90",
        "8177fd4a98964e78bbde98c53c6eb9ee475e37488cf68d970ea3980226e6ffc6",
    }),
    "1F393": frozenset({
        "4aeac189ebe73d1dacdaca41d3b83a93eb7d6aecc82390574cfee8afc8c64ace",
        "bbe625be30cb7d8e6ecc1b3cbeaf3edf54fcd7c54c294b79f2addd5850ca0e1d",
        "fff6e5be6fef333accbeddf0983d7cc4238b20a3a23cfe559416b6caa0a8f3c4",
    }),
    "221A": frozenset({
        "330b08fef3448d07e2432180a72bc6b0723da91d05bf6d59e30a3d9bffa40b5b",
        "3a175822ab5f3425eec72f1d26f0bbbfacb9f1671721bab4d3ef0cd550e04bb4",
        "756bc8becfc59a7af0ad51f36213e94af8469975163f8438e653e07c799486a7",
        "7c4a0070804773676105e104617ec2b734807c7ca02a78029fb2acb5aa6d3b9c",
        "88399d94f234d8c5cc50d8828097d034fb4349253d95e42b2e135e3ba9f1af8b",
    }),
    "003F": frozenset({
        "2349de9cc8755fd2bc909affa477039eda10bd9cd9f3bbfa26f3484a46b15eee",
        "bc9c06a04576a5f0f40bf1d60a55f0e8e94294f2fda3fd8fbb00b4ea115a0414",
        "edac5bf1e74e2cb32d4ac55b72e67cdd9473c46d5f4a0500de08a9b98e1f84b6",
    }),
    "1F6E0": frozenset({
        "35101f202fcdc18b044a2742640e4a7228bd849a6443b1e46e988a46aa081819",
        "720ef3e9228fa6e6cfd6dc52a9d2ebe8324d2cacd38dcd8602943e6262759a9a",
        "a4fe178970c9f9a335ee1afa171d08227bed74f786db521b6473e905ec1fba5f",
    }),
}
"""Codepoint → Hashes aller früheren Standard-Legenden dieses Symbols."""


def legend_fingerprint(one: str, two: str, three: str) -> str:
    """Hash einer Legende in der Form von :data:`LEGACY_LEGEND_SHA256`.

    Args:
        one: Text der Stufe 1.
        two: Text der Stufe 2.
        three: Text der Stufe 3.
    """
    text = "\n".join(part.strip() for part in (one, two, three))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
