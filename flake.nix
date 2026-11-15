{
  description = "status.kisen.one: kisenone の今の状態とサービスの死活を出すページ";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      checks.${system}.unit = pkgs.runCommand "kisenone-status-unit"
        { nativeBuildInputs = [ pkgs.python3 ]; } ''
        cp -r ${./kisenone_status} kisenone_status
        cp -r ${./tests} tests
        python3 -m unittest discover -s tests -t . -v
        touch $out
      '';
    };
}
