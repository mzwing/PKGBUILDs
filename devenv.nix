{pkgs, lib, ...}: {
  languages.shell = {
    enable = true;
    lsp.enable = true;
  };

  languages.python = {
    enable = true;
    directory = ".";

    venv.enable = true;

    uv = {
      enable = true;
      sync.enable = true;
    };

    lsp = {
      enable = true;
      package = pkgs.ty;
    };
  };

  packages = with pkgs;
    [
      nvchecker
      shfmt
    ]
    ++ lib.optionals stdenv.hostPlatform.isLinux [
      pacman
    ];

  enterTest = ''
    bash-language-server --version
    nvchecker --version
    shfmt --version
    python --version
    uv --version
    ty --version
    ${lib.optionalString pkgs.stdenv.hostPlatform.isLinux "makepkg --version"}
  '';
}
