{ fetchurl }:

{
  # 国土数値情報 (行政区域) を都道府県単位・1% に簡略化したもの (smartnews-smri/japan-topography)。
  # 利用には「国土数値情報 (行政区域データ) (国土交通省) を加工して作成」の出典表示が要る
  geoJp = fetchurl {
    url = "https://raw.githubusercontent.com/smartnews-smri/japan-topography/955608ab585a4892cc29a2cf043912d882e86041/data/municipality/geojson/s0010/prefectures.json";
    hash = "sha256-I0kU7joTvupu8l8Ujlw6G6bQ0fDQ2Osq9qFzJ5Ls8+0=";
  };
  # Natural Earth 1:50m admin-0 (public domain)
  geoWorld = fetchurl {
    url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_50m_admin_0_countries.geojson";
    hash = "sha256-PkWPwDatCmZBHywebKxJxde/uByxEjvFE7IlEaK3/es=";
  };
  # Natural Earth 1:10m time zones (public domain)。zone は UTC からの時間
  geoTz = fetchurl {
    url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_time_zones.geojson";
    hash = "sha256-qlKrl+X5Bmk/Mf4uYlyda+eKTnT81BQqcmEjWzVcrP4=";
  };
}
