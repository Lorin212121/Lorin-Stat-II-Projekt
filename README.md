# Lorin-Stat-II-Projekt

Ein Projekt von Lorin Büchel im Modul "STAT02" der HSLU

# Ziel des Projekts:

Analyse von Fahrdaten von Zügen, um den Einfluss verschiedener Faktoren auf die Pünktlichkeit von Zügen an den 10 grössten Schweizer Bahnhöfen im Jahr 2025 zu ermitteln. Das Projekt soll folgende Fragen beantworten:

1. Welche der Faktoren Bahnhof, Zugtyp, Tageszeit und Wochentag haben den grössten Einfluss auf die Abfahrtsverspätung an den 10 grössten Schweizer Bahnhöfen?
2. Welcher der 10 grössten Schweizer Bahnhöfe weist unter Berücksichtigung von Zugtyp, Tageszeit und Wochentag die grösste durchschnittliche Abfahrtsverspätung auf? 


Beantwortet werden diese Fragen mit multipler linearer Regression. Die Prädiktoren sind der Abfahrtsbahnhof, der Zugtyp (IC, IR, RE, R, S, und Internationale Züge), die Tageszeit und der Wochentag. Die Zielvariable ist die Abfahrtsverspätung in Minuten. Untersucht werden alle Abfahrten an den 10 Bahnhöfen, unabhängig davon, ob der Zug dort startet oder durchfährt. 

# Daten:

Grundlage sind die Ist-Daten des Schweizer öffentlichen Verkehrs für das Jahr 2025, bezogen aus dem Archiv von opentransportdata.swiss (https://archive.opentransportdata.swiss/actual_data_archive.htm#2025). Sie enthalten für jeden Halt jeder Fahrt die geplante und die tatsächliche Ankunfts- und Abfahrtszeit.

# Vorgehen:

1. Datenaufbereitung: Die Tagesdateien werden gefiltert auf Züge mit Abfahrt an einem der 10 untersuchten Bahnhöfe. Ausgefallene Züge, Durchfahrten ohne Halt und Abfahrten ohne gemessene Zeit (Status ≠ REAL) werden entfernt. Behalten werden Bahnhof, Datum, Zugtyp sowie geplante und tatsächliche Abfahrtszeit. Daraus werden die Abfahrtsverspätung in Minuten, der Wochentag (aus dem Datum) und die Tageszeit (Stunde der geplanten Abfahrt) berechnet. Alle Abfahrten werden in einem gemeinsamen Datensatz gespeichert.
2. Power-Analyse: Mit einer Power-Analyse wird geprüft, ob die Stichprobengrösse pro Bahnhof ausreicht, um einen relevanten Unterschied der Verspätung zwischen den Bahnhöfen signifikant nachzuweisen. Da an grossen Bahnhöfen täglich mehrere hundert bis über tausend Züge abfahren, wird ein ausreichend grosses n erwartet.
3. Signifikanzniveau und Power definieren: Verwendet werden das Signifikanzniveau α = 0.05 und eine angestrebte Power von 1 − β = 0.80, entsprechend den üblichen Konventionen nach Cohen (1988).
4. Analyse: Die Fragestellungen werden mit multipler linearer Regression (OLS) in Python (statsmodels) beantwortet: Verspätung ~ Bahnhof + Zugtyp + Tageszeit + Wochentag, alle als Dummy-Variablen. Für Frage 1 wird der Zuwachs des adjustierten R² pro Faktor verglichen, für Frage 2 die Bahnhofskoeffizienten. Dargestellt werden Koeffizienten mit Konfidenzintervallen, adjustiertes R² und eine Residuenanalyse. Wegen der grossen Stichprobe wird vor allem die Effektgrösse interpretiert. Die Ergebnisse werden in einem separaten PDF-Bericht festgehalten.

# Literaturverzeichnis:
Cohen, J. (1988). Statistical power analysis for the behavioral sciences (2nd ed.). Routledge. https://doi.org/10.4324/9780203771587