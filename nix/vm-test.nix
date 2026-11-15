{ pkgs, module }:

let
  keys = import "${pkgs.path}/nixos/tests/ssh-keys.nix" pkgs;
in
{
  name = "kisenone-status";

  nodes.machine = {
    imports = [ module ];
    services.openssh.enable = true;
    services.kisenone-status = {
      enable = true;
      pushKeys = [ keys.snakeOilPublicKey ];
      services = [
        { name = "sshd"; check = { type = "systemd"; target = "sshd.service"; }; }
        { name = "closed"; private = true; check = { type = "tcp"; target = "127.0.0.1:9"; }; }
      ];
    };
  };

  testScript = ''
    import json

    machine.wait_for_unit("sshd.service")
    machine.wait_for_unit("nginx.service")
    machine.succeed("install -m 600 ${keys.snakeOilPrivateKey} /root/key")
    # ssh の stdin と stdout を test driver の shell につなぐと終わらなくなるので、-n と >&2 で切り離す
    ssh = "ssh -n -i /root/key -o StrictHostKeyChecking=no -o BatchMode=yes kisenone-status@localhost"

    now = machine.succeed("date +%s").strip()
    machine.succeed(f"{ssh} computering {now} >&2", timeout=30)
    # forced command なので、渡したコマンドは実行されず push の入力として拒否される
    machine.fail(f"{ssh} 'touch /tmp/pwned' >&2", timeout=30)
    machine.fail("test -e /tmp/pwned")
    machine.fail(f"{ssh} hacking {now} >&2", timeout=30)

    machine.succeed("systemctl start kisenone-status-collect.service")
    status = json.loads(machine.succeed("curl -sf http://127.0.0.1:8087/status.json"))
    assert status["human"]["state"] == "computering", status
    assert {s["name"]: s["up"] for s in status["services"]} == {"sshd": True, "closed": False}, status
    assert "url" not in status["services"][1], status
    machine.succeed("curl -sf http://127.0.0.1:8087/ | grep -q kisenone")
  '';
}
