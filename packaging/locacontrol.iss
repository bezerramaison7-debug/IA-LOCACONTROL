; Instalador do LocaControl (P1-E, ADR-026). Compilar: scripts\installer.ps1 (Inno Setup 6).
; Programa em {autopf}\LocaControl; dados em {commonappdata}\LocaControl, nunca removidos sem
; confirmação explícita. Instalação silenciosa (CI, implantação):
;   LocaControl-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /MODO=principal /REDE=1
;   LocaControl-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /MODO=estacao /SERVIDOR=192.168.0.10 /CODIGO=...
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist-app\LocaControl"
#endif

[Setup]
AppId={{6F3B2A1C-4D5E-4F60-9A7B-8C1D2E3F4A5B}
AppName=LocaControl
AppVersion={#AppVersion}
AppPublisher=LocaControl
DefaultDirName={autopf}\LocaControl
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist-installer
OutputBaseFilename=LocaControl-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
; Atualização: fecha o LocaControl em execução antes de trocar os arquivos.
CloseApplications=force
RestartApplications=no
UninstallDisplayIcon={app}\LocaControl.exe
UninstallDisplayName=LocaControl
WizardStyle=modern
SetupLogging=yes

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Dirs]
; Os dados ficam fora do programa e nunca são apagados pela desinstalação automática.
Name: "{commonappdata}\LocaControl"; Permissions: users-modify; Flags: uninsneveruninstall

[Icons]
Name: "{autoprograms}\LocaControl"; Filename: "{app}\LocaControl.exe"
Name: "{autodesktop}\LocaControl"; Filename: "{app}\LocaControl.exe"
Name: "{commonstartup}\LocaControl (servidor)"; Filename: "{app}\LocaControl.exe"; Parameters: "servir"; Check: IsPrincipal

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""LocaControl (HTTPS da loja)"""; Flags: runhidden; Check: IsPrincipal
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""LocaControl (HTTPS da loja)"" dir=in action=allow protocol=TCP localport=8443 remoteip=localsubnet profile=private,domain program=""{app}\LocaControl.exe"""; Flags: runhidden; Check: IsPrincipal and NetworkEnabled
Filename: "{app}\LocaControl.exe"; Description: "Abrir o LocaControl agora"; Flags: postinstall nowait skipifsilent; Check: IsPrincipal

[UninstallRun]
Filename: "{app}\LocaControl.exe"; Parameters: "parar"; Flags: runhidden waituntilterminated; RunOnceId: "parar"
Filename: "{app}\LocaControl.exe"; Parameters: "desconectar"; Flags: runhidden waituntilterminated; RunOnceId: "desconectar"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""LocaControl (HTTPS da loja)"""; Flags: runhidden; RunOnceId: "firewall"

[Registry]
Root: HKLM; Subkey: "Software\LocaControl"; ValueType: string; ValueName: "Modo"; ValueData: "{code:ModeValue}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\LocaControl"; ValueType: string; ValueName: "Rede"; ValueData: "{code:NetworkValue}"
Root: HKLM; Subkey: "Software\LocaControl"; ValueType: string; ValueName: "Servidor"; ValueData: "{code:ServerAddress}"

[Code]
var
  ModePage: TInputOptionWizardPage;
  NetworkPage: TInputOptionWizardPage;
  StationPage: TInputQueryWizardPage;

function PreviousValue(Name, Default: String): String;
begin
  if not RegQueryStringValue(HKLM, 'Software\LocaControl', Name, Result) then
    Result := Default;
end;

function Param(Name, Default: String): String;
begin
  Result := ExpandConstant('{param:' + Name + '|' + Default + '}');
end;

procedure InitializeWizard;
begin
  ModePage := CreateInputOptionPage(wpWelcome, 'Como este computador vai usar o LocaControl?',
    'Escolha uma opção. Ela pode ser trocada reinstalando.',
    'Os dados da loja ficam sempre num único computador, o principal.', True, False);
  ModePage.Add('Usar neste computador (este é o computador principal, onde ficam os dados)');
  ModePage.Add('Conectar à loja (este computador é uma estação; os dados ficam no principal)');
  if Param('MODO', PreviousValue('Modo', 'principal')) = 'estacao' then
    ModePage.SelectedValueIndex := 1
  else
    ModePage.SelectedValueIndex := 0;

  NetworkPage := CreateInputOptionPage(ModePage.ID, 'Rede da loja',
    'Outros computadores da loja vão usar este?',
    'Com a rede ligada, as estações pareadas acessam este computador por HTTPS (porta 8443), só na rede local.',
    False, False);
  NetworkPage.Add('Permitir que outros computadores da loja usem este');
  NetworkPage.Values[0] := Param('REDE', PreviousValue('Rede', '0')) = '1';

  StationPage := CreateInputQueryPage(ModePage.ID, 'Conectar à loja',
    'Endereço do computador principal e código de pareamento',
    'No computador principal, abra Gestão → Estações da rede e clique em Gerar código. ' +
    'O código confirma que o certificado de segurança é mesmo do computador principal.');
  StationPage.Add('Endereço do computador principal (IP ou nome):', False);
  StationPage.Add('Código de pareamento:', False);
  StationPage.Values[0] := Param('SERVIDOR', PreviousValue('Servidor', ''));
  StationPage.Values[1] := Param('CODIGO', '');
end;

function IsStation: Boolean;
begin
  Result := ModePage.SelectedValueIndex = 1;
end;

function IsPrincipal: Boolean;
begin
  Result := not IsStation;
end;

function NetworkEnabled: Boolean;
begin
  Result := IsPrincipal and NetworkPage.Values[0];
end;

function ModeValue(Param: String): String;
begin
  if IsStation then Result := 'estacao' else Result := 'principal';
end;

function NetworkValue(Param: String): String;
begin
  if NetworkEnabled then Result := '1' else Result := '0';
end;

function ServerAddress(Param: String): String;
begin
  Result := Trim(StationPage.Values[0]);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := ((PageID = NetworkPage.ID) and IsStation) or ((PageID = StationPage.ID) and IsPrincipal);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = StationPage.ID) and ((ServerAddress('') = '') or (Trim(StationPage.Values[1]) = '')) then
  begin
    MsgBox('Informe o endereço do computador principal e o código de pareamento.', mbError, MB_OK);
    Result := False;
  end;
end;

{ Grava só as chaves que o instalador escolhe no .env da pasta de dados; o resto é preservado. }
procedure SetEnv(Key, Value: String);
var
  Lines: TArrayOfString;
  Path: String;
  I: Integer;
  Found: Boolean;
begin
  Path := ExpandConstant('{commonappdata}\LocaControl\.env');
  if not LoadStringsFromFile(Path, Lines) then SetArrayLength(Lines, 0);
  Found := False;
  for I := 0 to GetArrayLength(Lines) - 1 do
    if Pos(Key + '=', Trim(Lines[I])) = 1 then
    begin
      Lines[I] := Key + '=' + Value;
      Found := True;
    end;
  if not Found then
  begin
    SetArrayLength(Lines, GetArrayLength(Lines) + 1);
    Lines[GetArrayLength(Lines) - 1] := Key + '=' + Value;
  end;
  SaveStringsToUTF8File(Path, Lines, False);
end;

function SilentFlag: String;
begin
  if WizardSilent then Result := ' --sem-navegador' else Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
    Exec(ExpandConstant('{app}\LocaControl.exe'), 'parar', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if CurStep = ssPostInstall then
  begin
    if IsPrincipal then
    begin
      SetEnv('LOCACONTROL_LOCAL_MODE', 'true');
      if NetworkEnabled then SetEnv('LOCACONTROL_NETWORK_MODE', 'true')
      else SetEnv('LOCACONTROL_NETWORK_MODE', 'false');
    end
    else
    begin
      { A estação confere a identidade do principal com o código antes de confiar no certificado. }
      if not Exec(ExpandConstant('{app}\LocaControl.exe'),
        'conectar --servidor "' + ServerAddress('') + '" --codigo "' + Trim(StationPage.Values[1]) + '"' +
        SilentFlag, '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
        or (ResultCode <> 0) then
        SuppressibleMsgBox('Não foi possível conectar à loja (código ' + IntToStr(ResultCode) + '). ' +
          'Nenhum certificado foi instalado. Confira o endereço e gere um novo código no computador ' +
          'principal e execute o instalador de novo. Detalhes: ' +
          ExpandConstant('{commonappdata}\LocaControl\logs\comandos.log'), mbError, MB_OK, IDOK);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
  begin
    DataDir := ExpandConstant('{commonappdata}\LocaControl');
    if DirExists(DataDir) and
      (MsgBox('Os dados da loja (banco, contratos, documentos e backups) foram mantidos em ' + DataDir +
        '.' + #13#10#13#10 + 'Deseja EXCLUIR também esses dados? Isso não pode ser desfeito.',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) and
      (MsgBox('Confirme: excluir definitivamente todos os dados comerciais de ' + DataDir + '?',
        mbCriticalError, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
      DelTree(DataDir, True, True, True);
  end;
end;
