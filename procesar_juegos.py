import argparse
from pathlib import Path
import re

import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer


BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "data" / "game_info_cleaned.csv"
OUTPUT_PATH = BASE_DIR / "dataset_juegos_limpio.csv"

REGLAS = {
    "es_game_jam": r"\b(?:ludum(?:[- ]?dare)?|ld\d*|ggj|global[- ]?game[- ]?jam|gmtk|game[- ]?jam|jam)\b",
    "soporta_windows": r"\b(?:win(?:32|64)?|windows|pc|exe)\b",
    "soporta_mac": r"\b(?:mac(?:os)?|osxa?|os x)\b",
    "soporta_html5": r"\b(?:html5|browser|webgl?|web-browser)\b",
    "es_demo": r"\bdemo\b",
}


def limpiar_texto(valor: object) -> str:
    """Quita controles, bloques gráficos y fragmentos que parecen memoria/binario."""
    if pd.isna(valor):
        return ""
    texto = str(valor).replace("||", " ")
    texto = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", texto)
    texto = re.sub(r"[\u2500-\u259F]", " ", texto)
    texto = re.sub(r"\b0x[0-9a-f]{6,}\b", " ", texto, flags=re.I)
    texto = re.sub(r"\b[A-Za-z0-9+/]{32,}={0,2}\b", " ", texto)
    texto = re.sub(r"([^\w\s])\1{4,}", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def limpiar_slug(valor: object) -> str:
    """Preserva el identificador de origen y solo quita espacios exteriores."""
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def slugificar(nombre: str) -> str:
    nombre = nombre.lower().strip()
    nombre = re.sub(r"[^a-z0-9]+", "-", nombre)
    return nombre.strip("-")


def construir_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Extrae slugs y convierte los tokens observados en casillas binarias."""
    columnas_busqueda = [
        columna
        for columna in df.columns
        if columna.lower() in {"slug", "name", "platforms", "genres", "developers", "publishers", "website", "esrb_rating", "tags", "events", "builds"}
        or any(pista in columna.lower() for pista in ("tag", "platform", "event", "build"))
    ]
    if not columnas_busqueda:
        raise ValueError("La fuente debe incluir al menos slug, name o campos de etiquetas.")

    limpio = df.copy()
    for columna in columnas_busqueda:
        limpiador = limpiar_slug if columna.lower() == "slug" else limpiar_texto
        limpio[columna] = limpio[columna].map(limpiador)

    nombres = limpio["name"] if "name" in limpio else pd.Series("", index=limpio.index)
    if "slug" in limpio:
        slugs = limpio["slug"].where(limpio["slug"].ne(""), nombres.map(slugificar))
    else:
        slugs = nombres.map(slugificar)

    columnas_identidad = [
        columna for columna in columnas_busqueda if columna.lower() in {"slug", "name"}
    ]
    columnas_eventos = columnas_identidad + [
        columna
        for columna in columnas_busqueda
        if columna.lower() == "genres"
        or any(pista in columna.lower() for pista in ("tag", "event", "build"))
    ]
    columnas_plataformas = columnas_identidad + [
        columna
        for columna in columnas_busqueda
        if "platform" in columna.lower()
        or any(pista in columna.lower() for pista in ("tag", "build"))
    ]
    texto_eventos = limpio[list(dict.fromkeys(columnas_eventos))].fillna("").agg(" ".join, axis=1)
    texto_plataformas = limpio[list(dict.fromkeys(columnas_plataformas))].fillna("").agg(" ".join, axis=1)
    etiquetas = [
        [
            nombre
            for nombre, patron in REGLAS.items()
            if re.search(
                patron,
                texto_plataformas.iloc[indice]
                if nombre.startswith("soporta_")
                else texto_eventos.iloc[indice],
                flags=re.I,
            )
        ]
        for indice in limpio.index
    ]
    codificador = MultiLabelBinarizer(classes=list(REGLAS))
    indicadores = pd.DataFrame(
        codificador.fit_transform(etiquetas),
        columns=list(REGLAS),
        index=limpio.index,
        dtype=bool,
    )

    resultado = pd.concat(
        [slugs.rename("slug_juego"), indicadores],
        axis=1,
    )
    resultado = resultado[resultado["slug_juego"].ne("")]
    return resultado.drop_duplicates(subset="slug_juego").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Limpia metadatos de videojuegos y genera casillas de plataformas/eventos."
    )
    parser.add_argument("--input", type=Path, default=INPUT_PATH, help="CSV de entrada")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="CSV de salida")
    args = parser.parse_args()

    fuente = pd.read_csv(args.input, low_memory=False)
    dataset = construir_dataset(fuente)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"Registros procesados: {len(dataset):,}")
    print(f"Juegos de Game Jam: {dataset['es_game_jam'].mean():.2%}")
    for plataforma in ("soporta_windows", "soporta_mac", "soporta_html5"):
        cantidad = int(dataset[plataforma].sum())
        print(f"{plataforma}: {cantidad:,} ({cantidad / len(dataset):.2%})")
    print(f"Archivo generado: {args.output}")
    print(dataset.head(15).to_string(index=False))


if __name__ == "__main__":
    main()