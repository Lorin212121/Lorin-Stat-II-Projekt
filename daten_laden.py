# %% [markdown]
# # Daten laden
# Lädt die Ist-Daten 2025 Monat für Monat aus dem Archiv von opentransportdata.swiss,
# filtert sie und speichert pro Monat ein kleines CSV in daten/gefiltert/.
# Ablauf pro Monat: ZIP herunterladen -> Tagesdateien filtern -> CSV speichern -> ZIP löschen.
#
# Die "# %%"-Zeilen sind Zellgrenzen. VS Code und Jupyter zeigen sie als einzelne Zellen an.

# %% Pakete
from pathlib import Path
from urllib.parse import urljoin
import zipfile

import pandas as pd
import requests
from bs4 import BeautifulSoup  # falls es fehlt: pip install beautifulsoup4

# %% Einstellungen
ARCHIV_URL = "https://archive.opentransportdata.swiss/actual_data_archive.htm"
JAHR = "2025"
LINK_FILTER = ""  # z.B. "v1", falls es pro Monat mehrere Versionen gibt (siehe Zelle "Links finden")

ROH = Path("daten/roh")              # hier landen die ZIPs kurzzeitig
GEFILTERT = Path("daten/gefiltert")  # hier landen die kleinen Monats-CSVs
ROH.mkdir(parents=True, exist_ok=True)
GEFILTERT.mkdir(parents=True, exist_ok=True)

# Testmodus: zuerst klein anfangen! Für den vollen Lauf beide auf None setzen.
MAX_MONATE = 1        # wie viele Monate verarbeiten
MAX_TAGE = 2          # wie viele Tagesdateien pro Monat
ZIP_LOESCHEN = False  # im Testmodus ZIP behalten, damit du nicht neu herunterladen musst

# Namen genau so, wie sie in der Spalte HALTESTELLEN_NAME stehen.
# Mit der Zelle "Bahnhofsnamen prüfen" kontrollieren!
BAHNHOEFE = [
    "Zürich HB",
    "Bern",
    "Basel SBB",
    "Genève",
    "Lausanne",
    "Luzern",
    "Winterthur",
    "Zürich Oerlikon",
    "Olten",
    "Zug",
]

# Nur diese Spalten werden eingelesen (spart viel Zeit und Speicher).
SPALTEN = [
    "BETRIEBSTAG",
    "PRODUKT_ID",
    "LINIEN_TEXT",
    "VERKEHRSMITTEL_TEXT",
    "HALTESTELLEN_NAME",
    "BPUIC",
    "ABFAHRTSZEIT",
    "AB_PROGNOSE",
    "AB_PROGNOSE_STATUS",
    "FAELLT_AUS_TF",
    "DURCHFAHRT_TF",
]

# Diese Spalten braucht es nur zum Filtern, danach fliegen sie raus.
NUR_ZUM_FILTERN = ["PRODUKT_ID", "AB_PROGNOSE_STATUS", "FAELLT_AUS_TF", "DURCHFAHRT_TF"]


# %% Links finden
def finde_zip_links():
    """Holt die Archivseite und gibt alle ZIP-Links für JAHR zurück."""
    antwort = requests.get(ARCHIV_URL, timeout=60)
    antwort.raise_for_status()
    soup = BeautifulSoup(antwort.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        url = urljoin(ARCHIV_URL, a["href"])  # macht aus relativen Links ganze URLs
        if url.lower().endswith(".zip") and JAHR in url and LINK_FILTER in url:
            links.append(url)
    return sorted(set(links))


links = finde_zip_links()
print(f"{len(links)} Links gefunden:")
for link in links:
    print(link)
# Erwartet: 12 Links (einer pro Monat). Sind es mehr, LINK_FILTER oben setzen.
# Sind es 0, werden die Links per JavaScript geladen, dann melde dich.


# %% Funktionen
def herunterladen(url, ziel):
    """Lädt eine grosse Datei Stück für Stück herunter."""
    if ziel.exists():
        print(f"  {ziel.name} ist schon da, Download übersprungen")
        return
    teil = ziel.with_suffix(".part")  # erst unter anderem Namen, damit ein Abbruch keine halbe ZIP hinterlässt
    with requests.get(url, stream=True, timeout=120) as antwort:
        antwort.raise_for_status()
        with open(teil, "wb") as f:
            for stueck in antwort.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(stueck)
    teil.rename(ziel)


def ist_wahr(spalte):
    """FAELLT_AUS_TF / DURCHFAHRT_TF enthalten 'true'/'false' als Text."""
    return spalte.fillna("").str.strip().str.lower().eq("true")


def filtere(df):
    """Behält nur die Zeilen, die wir für die Analyse brauchen."""
    df = df[df["HALTESTELLEN_NAME"].isin(BAHNHOEFE)]
    df = df[df["PRODUKT_ID"].fillna("").str.strip().str.lower().eq("zug")]
    df = df[df["AB_PROGNOSE_STATUS"].fillna("").str.strip().str.upper().eq("REAL")]
    df = df[~ist_wahr(df["FAELLT_AUS_TF"])]
    df = df[~ist_wahr(df["DURCHFAHRT_TF"])]
    df = df[df["ABFAHRTSZEIT"].notna() & df["AB_PROGNOSE"].notna()]  # nur echte Abfahrten
    return df.drop(columns=NUR_ZUM_FILTERN)


def verarbeite_tagesdatei(z, name):
    """Liest eine Tagesdatei aus der offenen ZIP in Häppchen und filtert jedes Häppchen sofort."""
    teile = []
    with z.open(name) as f:
        for chunk in pd.read_csv(f, sep=";", usecols=SPALTEN, dtype=str, chunksize=500_000):
            teile.append(filtere(chunk))
    return pd.concat(teile, ignore_index=True)


def verarbeite_monat(zip_pfad, ziel_csv):
    """Geht durch alle Tagesdateien einer Monats-ZIP und schreibt ein gefiltertes CSV."""
    tage = []
    with zipfile.ZipFile(zip_pfad) as z:  # "with" schliesst die ZIP am Ende automatisch
        namen = sorted(n for n in z.namelist() if n.lower().endswith(".csv"))
        if MAX_TAGE:
            namen = namen[:MAX_TAGE]
        for name in namen:
            try:
                tag = verarbeite_tagesdatei(z, name)
                tage.append(tag)
                print(f"  {name}: {len(tag):,} Zeilen behalten")
            except Exception as fehler:
                print(f"  FEHLER bei {name}: {fehler}")  # eine kaputte Datei stoppt nicht alles
    monat = pd.concat(tage, ignore_index=True)
    temp = ziel_csv.with_suffix(".tmp")
    monat.to_csv(temp, index=False)
    temp.rename(ziel_csv)  # erst am Schluss umbenennen: existiert die Datei, ist sie vollständig
    return len(monat)


# %% Hauptschleife
for url in links[:MAX_MONATE]:
    zip_pfad = ROH / url.split("/")[-1]
    ziel_csv = GEFILTERT / (zip_pfad.stem + ".csv")

    if ziel_csv.exists():
        print(f"{ziel_csv.name} ist schon fertig, übersprungen")
        continue

    print(f"Monat {zip_pfad.name}")
    herunterladen(url, zip_pfad)
    anzahl = verarbeite_monat(zip_pfad, ziel_csv)
    print(f"  -> {ziel_csv.name} gespeichert ({anzahl:,} Zeilen)")

    if ZIP_LOESCHEN:
        zip_pfad.unlink()  # erst löschen, nachdem das CSV sicher geschrieben ist
        print(f"  {zip_pfad.name} gelöscht")

print("Fertig.")


# %% Bahnhofsnamen prüfen (einmal laufen lassen, nachdem die erste ZIP da ist)
def zeige_bahnhofsnamen(zip_pfad, suchwoerter):
    """Zeigt, wie die Bahnhöfe in der Datei wirklich heissen."""
    with zipfile.ZipFile(zip_pfad) as z:
        name = sorted(n for n in z.namelist() if n.lower().endswith(".csv"))[0]
        with z.open(name) as f:
            df = pd.read_csv(f, sep=";", usecols=["HALTESTELLEN_NAME", "PRODUKT_ID"], dtype=str)
    namen = df.loc[df["PRODUKT_ID"].str.lower() == "zug", "HALTESTELLEN_NAME"].dropna().unique()
    for wort in suchwoerter:
        treffer = sorted(n for n in namen if wort.lower() in n.lower())
        print(f"{wort}: {treffer}")


# zeige_bahnhofsnamen(next(ROH.glob("*.zip")), ["Zürich", "Bern", "Basel", "Gen", "Lausanne",
#                                               "Luzern", "Winterthur", "Olten", "Zug"])
