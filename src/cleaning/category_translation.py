import pandas as pd

MISSING_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_and_food_preparers",
    "unknown": "unknown",
}


def clean_category_translation(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    extra = pd.DataFrame({
        "product_category_name": list(MISSING_TRANSLATIONS.keys()),
        "product_category_name_english": list(MISSING_TRANSLATIONS.values()),
    })
    return pd.concat([df, extra], ignore_index=True)