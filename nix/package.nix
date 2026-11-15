{ lib, stdenvNoCC, python3, fetchurl, makeWrapper }:

let
  inherit (import ./geodata.nix { inherit fetchurl; }) geoJp geoWorld geoTz;
in
stdenvNoCC.mkDerivation {
  pname = "kisenone-status";
  version = "0.1.0";

  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [ ../kisenone_status ../web ];
  };

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall
    mkdir -p $out/bin $out/lib/kisenone-status $out/share/kisenone-status
    cp -r kisenone_status $out/lib/kisenone-status/
    cp -r web $out/share/kisenone-status/web
    for cmd in collect push; do
      makeWrapper ${python3}/bin/python3 $out/bin/kisenone-status-$cmd \
        --add-flags "-B -m kisenone_status.$cmd" \
        --set PYTHONPATH $out/lib/kisenone-status \
        --set KISENONE_GEO_JP ${geoJp} \
        --set KISENONE_GEO_WORLD ${geoWorld} \
        --set KISENONE_GEO_TZ ${geoTz}
    done
    runHook postInstall
  '';

  passthru = { inherit geoJp geoWorld geoTz; };

  meta = {
    description = "status.kisen.one: kisenone の今の状態とサービスの死活を出すページ";
    license = lib.licenses.mit;
    mainProgram = "kisenone-status-collect";
  };
}
