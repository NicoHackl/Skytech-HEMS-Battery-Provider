#!/bin/sh
# init-projekt.sh — kopiert die Vorlage aus Git-Template/vorlage in ein Zielprojekt
# und ersetzt die {{PLATZHALTER}}. Ueberschreibt vorhandene Dateien nur mit --force.
set -eu

SKRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VORLAGE="$SKRIPT_DIR/../vorlage"
FRONTEND_VORLAGE="$SKRIPT_DIR/../frontend"

ZIEL=""
NAME=""
ZWECK=""
BRANCH="agent/main"
STACK=""
INSTALL_BEFEHL=""
TEST_BEFEHL=""
LINT_BEFEHL=""
BUILD_BEFEHL=""
MINIMAL=0
SYMLINKS=0
FORCE=0
DRYRUN=0
FRONTEND=0
FRONTEND_ORDNER="web"
DESIGN=""
INPLACE=0
BESTAND=0

hilfe() {
    cat <<'ENDE'
Verwendung:
  init-projekt.sh <zielpfad> [optionen]     Vorlage in ein anderes Verzeichnis kopieren
  init-projekt.sh --in-place [optionen]     Dieses Repo selbst zum Projekt machen

Optionen:
  --name <text>       Projektname                        ({{PROJEKT_NAME}})
  --zweck <text>      Projektzweck, 1-3 Saetze           ({{PROJEKT_ZWECK}})
  --branch <name>     Arbeitsbranch, Default agent/main ({{ARBEITS_BRANCH}})
  --stack <text>      Tech-Stack                         ({{TECH_STACK}})
  --install <befehl>  Installationsbefehl                ({{INSTALL_BEFEHL}})
  --test <befehl>     Testbefehl                         ({{TEST_BEFEHL}})
  --lint <befehl>     Lintbefehl                         ({{LINT_BEFEHL}})
  --build <befehl>    Buildbefehl                        ({{BUILD_BEFEHL}})

  --design <sprache>  Designsprache, Pflicht bei --frontend:      ({{DESIGNSPRACHE}})
                      ha  = Home Assistant, Akzent #18BCF2
                      fcr = FC Ruderting, Vereinsfarben
                      Es gibt keinen Default. Passt keine der beiden,
                      wird beim Auftraggeber nachgefragt, nicht geraten.

  --in-place          Kein Zielpfad: die Vorlage wird in diesem Repo selbst
                      ausgerollt (vorlage/* wandert ins Wurzelverzeichnis) und
                      das Geruest danach entfernt — vorlage/, frontend/, bin/
                      und der Bootstrap-Command. Fuer den Ablauf
                      "Template kopieren, Initialprompt, loslegen".
  --bestand           Bestandsprojekt: KEINE vorhandene Datei wird angefasst,
                      auch keine der Bootstrap-Dateien. Ergaenzt nur, was fehlt,
                      und listet am Ende auf, was uebersprungen wurde — diese
                      Dateien werden von Hand zusammengefuehrt.
  --minimal           Nur AGENTS.md, Adapter und die vier wichtigsten docs-Dateien
  --frontend          Referenz-SPA mitkopieren (React + TS + Vite + Design-System)
  --frontend-ordner <name>
                      Zielordner der SPA, Default: web           ({{FRONTEND_ORDNER}})
  --symlinks          Adapterdateien als Symlink auf AGENTS.md statt als Pointer
  --force             Vorhandene Dateien ueberschreiben
  --dry-run           Nur anzeigen, nichts schreiben
  -h, --help          Diese Hilfe

Nicht gesetzte Platzhalter bleiben als {{...}} stehen, damit sie sichtbar offen sind.

Beispiel:
  init-projekt.sh ../MeinProjekt --name "Mein Projekt" \
      --stack "Python 3.11, aiohttp" --test "pytest" --lint "ruff check ."

  init-projekt.sh ../MeinProjekt --name "Mein Projekt" --frontend
ENDE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --name)     NAME="${2:?--name braucht einen Wert}"; shift 2 ;;
        --zweck)    ZWECK="${2:?--zweck braucht einen Wert}"; shift 2 ;;
        --branch)   BRANCH="${2:?--branch braucht einen Wert}"; shift 2 ;;
        --stack)    STACK="${2:?--stack braucht einen Wert}"; shift 2 ;;
        --install)  INSTALL_BEFEHL="${2:?--install braucht einen Wert}"; shift 2 ;;
        --test)     TEST_BEFEHL="${2:?--test braucht einen Wert}"; shift 2 ;;
        --lint)     LINT_BEFEHL="${2:?--lint braucht einen Wert}"; shift 2 ;;
        --build)    BUILD_BEFEHL="${2:?--build braucht einen Wert}"; shift 2 ;;
        --design)
            DESIGN="${2:?--design braucht einen Wert: ha oder fcr}"
            case "$DESIGN" in
                ha|fcr) ;;
                *) echo "Unbekannte Designsprache: $DESIGN (erlaubt: ha, fcr)" >&2; exit 2 ;;
            esac
            shift 2 ;;
        --in-place) INPLACE=1; shift ;;
        --bestand)  BESTAND=1; shift ;;
        --minimal)  MINIMAL=1; shift ;;
        --frontend) FRONTEND=1; shift ;;
        --frontend-ordner)
            FRONTEND=1
            FRONTEND_ORDNER="${2:?--frontend-ordner braucht einen Wert}"; shift 2 ;;
        --symlinks) SYMLINKS=1; shift ;;
        --force)    FORCE=1; shift ;;
        --dry-run)  DRYRUN=1; shift ;;
        -h|--help)  hilfe; exit 0 ;;
        -*)         echo "Unbekannte Option: $1" >&2; hilfe >&2; exit 2 ;;
        *)
            if [ -n "$ZIEL" ]; then
                echo "Mehr als ein Zielpfad angegeben: '$ZIEL' und '$1'" >&2
                exit 2
            fi
            ZIEL="$1"; shift ;;
    esac
done

# --in-place arbeitet immer in der Wurzel dieses Repos; ein zweiter Zielpfad
# waere widerspruechlich.
if [ "$INPLACE" -eq 1 ]; then
    case "$ZIEL" in
        ''|.|"$SKRIPT_DIR/..") ZIEL=$(CDPATH= cd -- "$SKRIPT_DIR/.." && pwd) ;;
        *) echo "--in-place vertraegt keinen Zielpfad ('$ZIEL')." >&2; exit 2 ;;
    esac
fi

[ -n "$ZIEL" ] || { echo "Kein Zielpfad angegeben." >&2; hilfe >&2; exit 2; }
[ -d "$VORLAGE" ] || { echo "Vorlage nicht gefunden: $VORLAGE" >&2; exit 1; }

# Eine Oberflaeche ohne festgelegte Designsprache gibt es nicht — und geraten
# wird sie nicht. Ohne --frontend bleibt {{DESIGNSPRACHE}} sichtbar offen.
if [ "$FRONTEND" -eq 1 ] && [ -z "$DESIGN" ]; then
    echo "--frontend braucht --design: ha (Home Assistant) oder fcr (FC Ruderting)." >&2
    echo "Passt keines von beiden, erst beim Auftraggeber nachfragen." >&2
    exit 2
fi

# Berliner Zeit und Format TT.MM.JJJJ — eiserne Regel 9 in AGENTS.md
JAHR=$(TZ=Europe/Berlin date +%Y)
DATUM=$(TZ=Europe/Berlin date +%d.%m.%Y)

TMP=$(mktemp -d) || { echo "Konnte kein temporaeres Verzeichnis anlegen." >&2; exit 1; }
trap 'rm -rf "$TMP"' EXIT INT TERM

# --- Dateilisten ------------------------------------------------------------

# Was --minimal uebrig laesst (Pfade relativ zur Vorlagenwurzel).
# architektur.md, bekannte-luecken.md und adr/0000-vorlage.md sind dabei, weil der
# Arbeitsablauf in AGENTS.md aktiv anweist, sie zu lesen — ohne sie waere die
# Anweisung nicht ausfuehrbar. nutzertexte.md ebenso: eiserne Regel 12 verweist
# darauf, und sie gilt auch fuer Projekte ganz ohne Oberflaeche (CLI, Logs).
cat > "$TMP/minimal" <<'ENDE'
AGENTS.md
CLAUDE.md
GEMINI.md
.github/copilot-instructions.md
.cursor/rules/00-agents.mdc
docs/README.md
docs/architektur.md
docs/entwicklerrichtlinien.md
docs/nutzertexte.md
docs/git-workflow.md
docs/design-entscheidungen.md
docs/bekannte-luecken.md
docs/adr/0000-vorlage.md
CHANGELOG.md
ENDE

# Mit --frontend sind die Frontend-Regeln Pflichtlektuere — dann duerfen sie
# auch bei --minimal nicht fehlen, sonst verweist AGENTS.md ins Leere.
if [ "$FRONTEND" -eq 1 ]; then
    printf 'docs/frontend.md\ndocs/design-system.md\n' >> "$TMP/minimal"
fi

# Adapterdateien und ihr Symlink-Ziel, von der Adapterdatei aus gesehen
cat > "$TMP/adapter" <<'ENDE'
CLAUDE.md AGENTS.md
GEMINI.md AGENTS.md
.github/copilot-instructions.md ../AGENTS.md
ENDE

# Bootstrap-Dateien: liegen im Template bereits in der Wurzel und sagen jeder KI,
# dass das Repo noch einzurichten ist. Bei --in-place werden genau diese ersetzt,
# auch ohne --force — sie gehoeren dem Template, nicht dem Projekt. Alles andere
# bleibt geschuetzt, damit ein Init in einem schon befuellten Repo nichts frisst.
cat > "$TMP/bootstrap" <<'ENDE'
AGENTS.md
CLAUDE.md
GEMINI.md
README.md
.github/copilot-instructions.md
.cursor/rules/00-agents.mdc
ENDE

# --- sed-Skript aufbauen ----------------------------------------------------
# Als Datei statt als Argumentliste: sonst zerfallen Werte mit Leerzeichen
# beim Wortsplitting ("--name 'Mein Projekt'").

: > "$TMP/ersetzungen.sed"

setze() {
    # $1 = Platzhaltername, $2 = Wert. Leerer Wert -> Platzhalter bleibt stehen.
    [ -n "$2" ] || return 0
    # | \ & im Ersatztext maskieren, damit sed sie nicht als Syntax deutet
    wert=$(printf '%s' "$2" | sed 's/[|\\&]/\\&/g')
    printf 's|{{%s}}|%s|g\n' "$1" "$wert" >> "$TMP/ersetzungen.sed"
}

setze PROJEKT_NAME    "$NAME"
setze PROJEKT_ZWECK   "$ZWECK"
setze ARBEITS_BRANCH  "$BRANCH"
setze TECH_STACK      "$STACK"
setze INSTALL_BEFEHL  "$INSTALL_BEFEHL"
setze TEST_BEFEHL     "$TEST_BEFEHL"
setze LINT_BEFEHL     "$LINT_BEFEHL"
setze BUILD_BEFEHL    "$BUILD_BEFEHL"
setze JAHR            "$JAHR"
setze DATUM           "$DATUM"

# Designsprache: Klartext in die Doku ({{DESIGNSPRACHE}}), Attributwert in die
# SPA ({{DESIGN}}). Ohne --design bleiben beide offen und der Akzent grau.
case "$DESIGN" in
    ha)  setze DESIGNSPRACHE "Home Assistant — Akzent \`#18BCF2\` (\`data-design=\"ha\"\`)" ;;
    fcr) setze DESIGNSPRACHE "FCR — Vereinsfarben FC Ruderting (\`data-design=\"fcr\"\`)" ;;
esac
setze DESIGN "$DESIGN"
# Ohne --frontend bleibt {{FRONTEND_ORDNER}} in docs/frontend.md sichtbar offen.
if [ "$FRONTEND" -eq 1 ]; then
    setze FRONTEND_ORDNER "$FRONTEND_ORDNER"
fi

# sed braucht mindestens einen Ausdruck
[ -s "$TMP/ersetzungen.sed" ] || printf 's|^|&|\n' > "$TMP/ersetzungen.sed"

# --- Kopieren ---------------------------------------------------------------

ANZ_NEU=0
ANZ_UEBERSPRUNGEN=0
: > "$TMP/uebersprungen"

if [ "$DRYRUN" -eq 1 ]; then
    echo "Probelauf — es wird nichts geschrieben."
fi
echo "Vorlage: $VORLAGE"
echo "Ziel:    $ZIEL"
echo ""

[ "$DRYRUN" -eq 1 ] || mkdir -p "$ZIEL"

# Dateiliste erst in eine Datei, damit die Schleife nicht in einer Subshell
# laeuft und die Zaehler erhalten bleiben.
# .DS_Store und AppleDouble-Reste ausschliessen: sed bricht an ihren Bytes ab
# ("illegal byte sequence") und reisst wegen set -e den ganzen Lauf mit.
find "$VORLAGE" -type f ! -name '.DS_Store' ! -name '._*' | sort > "$TMP/dateien"

while IFS= read -r datei; do
    rel=${datei#"$VORLAGE"/}

    if [ "$MINIMAL" -eq 1 ] && ! grep -qxF "$rel" "$TMP/minimal"; then
        continue
    fi

    ziel="$ZIEL/$rel"

    ueberschreibbar=$FORCE
    # Bootstrap-Dateien gehoeren dem Template und werden beim In-place-Init
    # ersetzt — ausser im Bestandsprojekt, wo dieselben Namen dem Projekt
    # gehoeren koennen (eine gewachsene README.md ueberschreibt man nicht).
    if [ "$INPLACE" -eq 1 ] && [ "$BESTAND" -eq 0 ] && grep -qxF "$rel" "$TMP/bootstrap"; then
        ueberschreibbar=1
    fi

    if { [ -e "$ziel" ] || [ -L "$ziel" ]; } && [ "$ueberschreibbar" -eq 0 ]; then
        ANZ_UEBERSPRUNGEN=$((ANZ_UEBERSPRUNGEN + 1))
        echo "  $rel" >> "$TMP/uebersprungen"
        continue
    fi

    linkziel=$(awk -v p="$rel" '$1 == p {print $2}' "$TMP/adapter")

    if [ "$SYMLINKS" -eq 1 ] && [ -n "$linkziel" ]; then
        if [ "$DRYRUN" -eq 1 ]; then
            echo "  symlink  $rel -> $linkziel"
        else
            mkdir -p "$(dirname "$ziel")"
            rm -f "$ziel"
            ln -s "$linkziel" "$ziel"
        fi
    else
        if [ "$DRYRUN" -eq 1 ]; then
            echo "  neu      $rel"
        else
            mkdir -p "$(dirname "$ziel")"
            sed -f "$TMP/ersetzungen.sed" "$datei" > "$ziel"
        fi
    fi
    ANZ_NEU=$((ANZ_NEU + 1))
done < "$TMP/dateien"

# --- Referenz-Frontend ------------------------------------------------------
# Nur mit --frontend, weil ein leeres SPA-Geruest in einem Projekt ohne
# Oberflaeche nur Rauschen waere. Struktur und Regeln: docs/frontend.md.

if [ "$FRONTEND" -eq 1 ]; then
    if [ ! -d "$FRONTEND_VORLAGE" ]; then
        echo "Frontend-Vorlage nicht gefunden: $FRONTEND_VORLAGE" >&2
        exit 1
    fi

    find "$FRONTEND_VORLAGE" -type f ! -name '.DS_Store' ! -name '._*' | sort > "$TMP/frontenddateien"

    while IFS= read -r datei; do
        rel="$FRONTEND_ORDNER/${datei#"$FRONTEND_VORLAGE"/}"
        ziel="$ZIEL/$rel"

        if { [ -e "$ziel" ] || [ -L "$ziel" ]; } && [ "$FORCE" -eq 0 ]; then
            ANZ_UEBERSPRUNGEN=$((ANZ_UEBERSPRUNGEN + 1))
            echo "  $rel" >> "$TMP/uebersprungen"
            continue
        fi

        if [ "$DRYRUN" -eq 1 ]; then
            echo "  neu      $rel"
        else
            mkdir -p "$(dirname "$ziel")"
            sed -f "$TMP/ersetzungen.sed" "$datei" > "$ziel"
        fi
        ANZ_NEU=$((ANZ_NEU + 1))
    done < "$TMP/frontenddateien"
fi

# --- Geruest entfernen (nur --in-place) -------------------------------------
# Nach dem Ausrollen ist der Generator kein Projektcode mehr. Bleibt er liegen,
# sieht ein Agent spaeter zwei AGENTS.md und muss raten, welche gilt. bin/ faellt
# ganz am Ende, weil dieses Skript darin liegt.

# Im Bestandsprojekt bleibt das Geruest stehen: die uebersprungenen Dateien
# muessen erst zusammengefuehrt werden, und die Vorlage ist dabei die Referenz.
# Aufgeraeumt wird dort erst nach der Migration, siehe Schlussbericht.

if [ "$INPLACE" -eq 1 ] && [ "$BESTAND" -eq 0 ] && [ "$DRYRUN" -eq 0 ]; then
    rm -rf "$ZIEL/vorlage" "$ZIEL/frontend"
    rm -f "$ZIEL/.claude/commands/projekt-init.md" "$ZIEL/.claude/commands/projekt-pruefen.md"
    # Leere Verzeichnisse nicht als Leiche zuruecklassen (rmdir schlaegt bei
    # gefuelltem Verzeichnis fehl — genau das ist hier die gewuenschte Pruefung).
    rmdir "$ZIEL/.claude/commands" 2>/dev/null || true
    rmdir "$ZIEL/.claude" 2>/dev/null || true
fi

# --- Tote Verweise bereinigen -----------------------------------------------
# Bei --minimal fehlen die meisten docs/-Dateien, die Verweistabellen in AGENTS.md
# und docs/README.md zeigen dann ins Leere. Ein toter Verweis in einer
# Agenten-Anweisung ist schaedlich: der Agent sucht eine Datei, die es nicht gibt.
# Darum: Tabellenzeilen mit totem Ziel entfernen, uebrige tote Links entlinken.

bereinige_tote_links() {
    find "$ZIEL" \( -name '*.md' -o -name '*.mdc' \) -type f > "$TMP/mdliste"

    while IFS= read -r datei; do
        verz=$(dirname "$datei")

        grep -o '](\([^)]*\))' "$datei" 2>/dev/null \
            | sed 's/^](//; s/)$//' | sort -u > "$TMP/links" || true

        : > "$TMP/tote"
        while IFS= read -r link; do
            case "$link" in
                ''|http:*|https:*|mailto:*|'#'*) continue ;;
            esac
            pfad=${link%%#*}
            [ -n "$pfad" ] || continue
            [ -e "$verz/$pfad" ] || echo "$pfad" >> "$TMP/tote"
        done < "$TMP/links"

        [ -s "$TMP/tote" ] || continue

        cp "$datei" "$TMP/arbeit"
        while IFS= read -r tot; do
            # Regex-Metazeichen im Zielpfad maskieren.
            m=$(printf '%s' "$tot" | sed 's/[.*[\^$\\]/\\&/g')
            # Fuer die Adresse /.../d zusaetzlich den / maskieren — sonst beendet
            # ein Pfadtrenner wie in "adr/" die Adresse vorzeitig.
            m_addr=$(printf '%s' "$m" | sed 's|/|\\/|g')

            # 1. Tabellenzeilen, deren Ziel fehlt, ganz entfernen
            sed "/^|.*](${m_addr})/d" "$TMP/arbeit" > "$TMP/arbeit2"
            mv "$TMP/arbeit2" "$TMP/arbeit"
            # 2. Uebrige tote Links entlinken: [Text](ziel) -> Text
            sed "s|\[\([^]]*\)\](${m})|\1|g" "$TMP/arbeit" > "$TMP/arbeit2"
            mv "$TMP/arbeit2" "$TMP/arbeit"
        done < "$TMP/tote"
        cp "$TMP/arbeit" "$datei"
    done < "$TMP/mdliste"
}

if [ "$DRYRUN" -eq 0 ] && [ "$MINIMAL" -eq 1 ]; then
    bereinige_tote_links
fi

# --- Bericht ----------------------------------------------------------------

echo ""
if [ "$DRYRUN" -eq 1 ]; then
    echo "$ANZ_NEU Datei(en) wuerden angelegt, $ANZ_UEBERSPRUNGEN uebersprungen."
else
    echo "$ANZ_NEU Datei(en) angelegt, $ANZ_UEBERSPRUNGEN uebersprungen."
fi

if [ "$ANZ_UEBERSPRUNGEN" -gt 0 ]; then
    echo ""
    if [ "$BESTAND" -eq 1 ]; then
        echo "Uebersprungen, weil im Projekt bereits vorhanden — diese Dateien"
        echo "von Hand zusammenfuehren (Regeln der Vorlage einarbeiten, nicht ersetzen):"
    else
        echo "Uebersprungen, weil bereits vorhanden (mit --force ueberschreiben):"
    fi
    cat "$TMP/uebersprungen"
fi

[ "$DRYRUN" -eq 1 ] && exit 0

# Das Geruest selbst enthaelt naturgemaess Platzhalter — es steht nur bei
# --bestand noch da und gehoert nicht in die Liste der offenen Punkte.
OFFEN=$(grep -rl '{{[A-Z_]*}}' "$ZIEL" 2>/dev/null \
    | grep -v "^$ZIEL/vorlage/" \
    | grep -v "^$ZIEL/frontend/" \
    | grep -v "^$ZIEL/bin/" \
    | sed "s|^$ZIEL/|  |" || true)
if [ -n "$OFFEN" ]; then
    echo ""
    echo "Noch offene Platzhalter in:"
    echo "$OFFEN"
fi

if [ "$INPLACE" -eq 1 ] && [ "$BESTAND" -eq 0 ]; then
    cat <<ENDE

Geruest entfernt: vorlage/, frontend/, .claude/commands/
Die Wurzel traegt jetzt die Projektfassung von AGENTS.md — die Bootstrap-Fassung
ist damit weg, jede KI liest ab sofort die echten Projektregeln.
ENDE
fi

if [ "$INPLACE" -eq 1 ] && [ "$BESTAND" -eq 1 ]; then
    cat <<'ENDE'

Bestandsprojekt: es wurde nichts ueberschrieben, das Geruest bleibt vorerst stehen.
Reihenfolge ab hier:
  1. Die oben aufgelisteten uebersprungenen Dateien zusammenfuehren — Regeln aus
     vorlage/ einarbeiten, gewachsene Inhalte behalten.
  2. Erst wenn nichts mehr aus vorlage/ gebraucht wird, aufraeumen:
     rm -rf vorlage frontend bin .claude/commands/projekt-init.md .claude/commands/projekt-pruefen.md
ENDE
fi

cat <<ENDE

Naechste Schritte:
  1. AGENTS.md ausfuellen — Zweck, Befehle, projekteigene Regeln
  2. Nicht zutreffende docs/-Dateien loeschen und aus docs/README.md austragen
  3. .env, .venv, node_modules, dist in .gitignore aufnehmen
  4. Regeln nur in AGENTS.md pflegen — nie in CLAUDE.md/GEMINI.md/copilot-instructions.md
ENDE

if [ "$FRONTEND" -eq 1 ]; then
    cat <<ENDE
  5. Frontend: cd $FRONTEND_ORDNER && npm install && npm run dev
     Designsprache: $DESIGN (data-design im index.html), Hell/Dunkel-Schalter
     sitzt in der Kopfzeile — beide Modi vor dem ersten Commit ansehen.
     Eine dritte Designsprache ist eine Design-Entscheidung: neuer
     data-design-Wert plus fuenf --primary-Tokens je Modus in src/styles.css,
     Eintrag in docs/design-entscheidungen.md. Ports in vite.config.ts setzen,
     Beispielseiten unter src/pages/ ersetzen.
ENDE
fi

# --- bin/ zuletzt ------------------------------------------------------------
# Loescht das Verzeichnis, in dem dieses Skript liegt. Das ist zulaessig: die
# Shell haelt den geoeffneten Dateideskriptor, der Inode ueberlebt das Unlink
# bis zum Ende des Laufs. Deshalb steht hier auch keine Zeile mehr danach.

if [ "$INPLACE" -eq 1 ] && [ "$BESTAND" -eq 0 ] && [ "$DRYRUN" -eq 0 ]; then
    rm -rf "$SKRIPT_DIR"
fi
