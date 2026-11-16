self:
{ config, lib, pkgs, ... }:

let
  cfg = config.services.kisenone-status;
  user = "kisenone-status";
  stateDir = "/var/lib/kisenone-status";
  publicDir = "${stateDir}/public";

  # services と machines の確かめ方。types は使える type の一覧
  checkOptions = types: {
    type = lib.mkOption {
      type = lib.types.enum types;
      description = "確かめ方。";
    };
    target = lib.mkOption {
      type = lib.types.str;
      description = "systemd なら unit 名、http なら URL、tcp なら host:port、push なら self か remote。";
    };
    headers = lib.mkOption {
      type = lib.types.attrsOf lib.types.str;
      default = { };
      description = "http のときに足すヘッダ。";
    };
  };

  serviceType = lib.types.submodule {
    options = {
      name = lib.mkOption {
        type = lib.types.str;
        description = "表示名。";
      };
      url = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "名前に付けるリンク。private のサービスには付けられない。";
      };
      private = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "名前と状態だけを出す。";
      };
      eventOnly = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "開催時だけ動くサービス。down のときは灰色で event only と出す。";
      };
      check = checkOptions [ "systemd" "http" "tcp" ];
    };
  };

  machineType = lib.types.submodule {
    options = {
      name = lib.mkOption {
        type = lib.types.str;
        description = "表示名。";
      };
      check = checkOptions [ "systemd" "http" "tcp" "push" ];
    };
  };

  configFile = pkgs.writeText "kisenone-status.json" (builtins.toJSON {
    state_dir = stateDir;
    public_dir = publicDir;
    utc_offset_minutes = cfg.utcOffsetMinutes;
    dawarich = if cfg.dawarich.url == null then null else { inherit (cfg.dawarich) url; };
    wakapi = if cfg.wakapi.url == null then null else { inherit (cfg.wakapi) url; };
    services = map (s: {
      inherit (s) name url private;
      event_only = s.eventOnly;
      check = { inherit (s.check) type target headers; };
    }) cfg.services;
    machines = map (m: {
      inherit (m) name;
      check = { inherit (m.check) type target headers; };
    }) cfg.machines;
  });
in
{
  options.services.kisenone-status = {
    enable = lib.mkEnableOption "status.kisen.one の collector と配信";

    package = lib.mkOption {
      type = lib.types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      defaultText = lib.literalExpression "kisenone-status.packages.\${system}.default";
      description = "使う kisenone-status のパッケージ。";
    };

    listen = {
      address = lib.mkOption {
        type = lib.types.str;
        default = "127.0.0.1";
        description = "nginx が listen するアドレス。";
      };
      port = lib.mkOption {
        type = lib.types.port;
        default = 8087;
        description = "nginx が listen するポート。";
      };
    };

    utcOffsetMinutes = lib.mkOption {
      type = lib.types.int;
      default = 540;
      description = "「今日」の区切りと時刻の表示に使う UTC からのずれ (分)。";
    };

    environmentFile = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "DAWARICH_API_KEY と WAKAPI_API_KEY を書いた env ファイル。LoadCredential で collector にだけ渡す。";
    };

    dawarich.url = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "http://127.0.0.1:3001";
      description = "Dawarich の URL。null なら位置を出さない。";
    };

    wakapi.url = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "http://127.0.0.1:3000";
      description = "Wakapi の URL。null ならコーディングの時間を出さない。";
    };

    services = lib.mkOption {
      type = lib.types.listOf serviceType;
      default = [ ];
      description = "死活を出すサービス。並び順のまま出す。";
    };

    machines = lib.mkOption {
      type = lib.types.listOf machineType;
      default = [ ];
      description = "死活を出すマシン。並び順のまま出す。push の self は push してくるマシン、remote はそのマシンが報告する ssh 先。";
    };

    pushKeys = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = "人間の状態を push する ssh 公開鍵。forced command 付きで専用ユーザーに入れる。";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = lib.all (s: !(s.private && s.url != null)) cfg.services;
        message = "services.kisenone-status.services: private のサービスに url は付けられない";
      }
      {
        assertion = lib.all (m: m.check.type != "push" || lib.elem m.check.target [ "self" "remote" ]) cfg.machines;
        message = "services.kisenone-status.machines: push の target は self か remote";
      }
    ];

    users.groups.${user} = { };
    users.users.${user} = {
      isSystemUser = true;
      group = user;
      home = stateDir;
      # forced command はログインシェル経由で実行されるので、nologin にはできない
      useDefaultShell = true;
      openssh.authorizedKeys.keys =
        map (key: ''command="${cfg.package}/bin/kisenone-status-push",restrict ${key}'') cfg.pushKeys;
    };

    systemd.tmpfiles.rules = [
      "d ${stateDir} 0755 ${user} ${user} - -"
      "d ${publicDir} 0755 ${user} ${user} - -"
    ];

    systemd.services.kisenone-status-collect = {
      description = "status.kisen.one の status.json を作る";
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];
      path = [ config.systemd.package ];
      environment.KISENONE_STATUS_CONFIG = configFile;
      serviceConfig = {
        Type = "oneshot";
        User = user;
        Group = user;
        ExecStart = "${cfg.package}/bin/kisenone-status-collect";
        LoadCredential = lib.optional (cfg.environmentFile != null) "env:${cfg.environmentFile}";
        ProtectSystem = "strict";
        ReadWritePaths = [ stateDir ];
        TimeoutStartSec = "2min";
        MemoryMax = "256M";
        PrivateDevices = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
        CapabilityBoundingSet = "";
        SystemCallFilter = [ "@system-service" ];
        ProtectHome = true;
        PrivateTmp = true;
        NoNewPrivileges = true;
      };
    };

    systemd.timers.kisenone-status-collect = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "30s";
        OnUnitActiveSec = "1min";
        AccuracySec = "5s";
      };
    };

    services.nginx = {
      enable = true;
      virtualHosts.kisenone-status = {
        listen = [ { addr = cfg.listen.address; port = cfg.listen.port; } ];
        root = "${cfg.package}/share/kisenone-status/web";
        extraConfig = ''
          add_header Cache-Control "public, max-age=300";
        '';
        locations."= /status.json" = {
          alias = "${publicDir}/status.json";
          extraConfig = ''
            add_header Cache-Control "public, max-age=30";
            add_header Access-Control-Allow-Origin "*";
          '';
        };
      };
    };
  };
}
