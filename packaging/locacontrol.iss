; Instalador do LocaControl (P1-E, ADR-026 e ADR-027). Compilar: scripts\installer.ps1 (Inno Setup 6).
; Programa em {autopf}\LocaControl; dados em {commonappdata}\LocaControl, nunca removidos sem
; confirmação explícita. No computador principal o servidor é o serviço do Windows "LocaControl",
; com identidade própria (NT SERVICE\LocaControl); a pasta de dados só é acessível a essa
; identidade, ao SYSTEM e aos administradores (SEC-P1E-01).
; Instalação silenciosa (CI, implantação):
;   LocaControl-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /MODO=principal /REDE=1
;   LocaControl-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /MODO=estacao /SERVIDOR=192.168.0.10 /CODIGO=...
; Códigos de saída próprios: 20 = estação não conectada à loja (nenhum certificado instalado);
; 21 = permissões da pasta de dados não aplicadas. O código 7 do Inno Setup (preparação falhou)
; inclui "o LocaControl em execução não terminou com segurança" (nada foi alterado).
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist-app\LocaControl"
#endif
#define ServiceName "LocaControl"
#define ServiceAccount "NT SERVICE\LocaControl"

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
; O servidor é encerrado de forma controlada em PrepareToInstall (REL-P1E-02); o Restart Manager só
; fecha o que sobrar (um "abrir" em uso, por exemplo).
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\LocaControl.exe
UninstallDisplayName=LocaControl
WizardStyle=modern
SetupLogging=yes

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs
Source: "data-acl.ps1"; DestDir: "{tmp}"; Flags: dontcopy

[Dirs]
; Os dados ficam fora do programa e nunca são apagados pela desinstalação automática. As
; permissões são definidas em ApplyDataAcl a cada instalação (não aqui).
Name: "{commonappdata}\LocaControl"; Flags: uninsneveruninstall

[InstallDelete]
; Versões anteriores iniciavam o servidor pela pasta Inicializar, como o usuário logado.
Type: files; Name: "{commonstartup}\LocaControl (servidor).lnk"

[Icons]
Name: "{autoprograms}\LocaControl"; Filename: "{app}\LocaControl.exe"
Name: "{autodesktop}\LocaControl"; Filename: "{app}\LocaControl.exe"

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""LocaControl (HTTPS da loja)"""; Flags: runhidden; Check: IsPrincipal
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""LocaControl (HTTPS da loja)"" dir=in action=allow protocol=TCP localport=8443 remoteip=localsubnet profile=private,domain program=""{app}\LocaControl.exe"""; Flags: runhidden; Check: IsPrincipal and NetworkEnabled
Filename: "{app}\LocaControl.exe"; Description: "Abrir o LocaControl agora"; Flags: postinstall nowait skipifsilent runasoriginaluser; Check: IsPrincipal
Filename: "{code:PairingAddress}"; Description: "Concluir o pareamento desta estação no navegador agora"; Flags: postinstall shellexec nowait skipifsilent runasoriginaluser; Check: StationConnected

[UninstallRun]
Filename: "{app}\LocaControl.exe"; Parameters: "parar"; Flags: runhidden waituntilterminated; RunOnceId: "parar"
Filename: "{sys}\sc.exe"; Parameters: "delete {#ServiceName}"; Flags: runhidden waituntilterminated; RunOnceId: "servico"
Filename: "{app}\LocaControl.exe"; Parameters: "desconectar"; Flags: runhidden waituntilterminated; RunOnceId: "desconectar"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""LocaControl (HTTPS da loja)"""; Flags: runhidden; RunOnceId: "firewall"

[Registry]
Root: HKLM; Subkey: "Software\LocaControl"; ValueType: string; ValueName: "Modo"; ValueData: "{code:ModeValue}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\LocaControl"; ValueType: string; ValueName: "Rede"; ValueData: "{code:NetworkValue}"
Root: HKLM; Subkey: "Software\LocaControl"; ValueType: string; ValueName: "Servidor"; ValueData: "{code:ServerAddress}"
Root: HKLM; Subkey: "Software\LocaControl"; ValueType: string; ValueName: "Porta"; ValueData: "{code:StorePort}"

[Code]
const
  EXIT_NOT_CONNECTED = 20;
  EXIT_ACL_FAILED = 21;

var
  ModePage: TInputOptionWizardPage;
  NetworkPage: TInputOptionWizardPage;
  StationPage: TInputQueryWizardPage;
  ResultPage: TInputQueryWizardPage;
  SkipConnect: TNewCheckBox;
  ConnectOk: Boolean;
  AclFailed: Boolean;
  ConnectMessage: String;
  PairUrl: String;

function PreviousValue(Name, Default: String): String;
begin
  if not RegQueryStringValue(HKLM, 'Software\LocaControl', Name, Result) then
    Result := Default;
end;

function Param(Name, Default: String): String;
begin
  Result := ExpandConstant('{param:' + Name + '|' + Default + '}');
end;

function DataDir: String;
begin
  Result := ExpandConstant('{commonappdata}\LocaControl');
end;

function AppExe: String;
begin
  Result := ExpandConstant('{app}\LocaControl.exe');
end;

function RunHidden(FileName, Params: String): Integer;
begin
  if not Exec(FileName, Params, '', SW_HIDE, ewWaitUntilTerminated, Result) then
    Result := -1;
  Log(Format('Executado: %s %s -> %d', [FileName, Params, Result]));
end;

function Sc(Params: String): Integer;
begin
  Result := RunHidden(ExpandConstant('{sys}\sc.exe'), Params);
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

  { Depois da cópia dos arquivos: resultado da conexão, com nova tentativa (UX-P1E-03). }
  ResultPage := CreateInputQueryPage(wpInfoAfter, 'Conectar à loja',
    'Não foi possível conectar este computador à loja', '');
  ResultPage.Add('Endereço do computador principal (IP ou nome):', False);
  ResultPage.Add('Novo código de pareamento:', False);
  SkipConnect := TNewCheckBox.Create(ResultPage);
  SkipConnect.Parent := ResultPage.Surface;
  SkipConnect.Top := ResultPage.Edits[1].Top + ResultPage.Edits[1].Height + ScaleY(16);
  SkipConnect.Width := ResultPage.SurfaceWidth;
  SkipConnect.Caption := 'Concluir sem conectar (este computador ficará sem acesso à loja)';
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

function StationConnected: Boolean;
begin
  Result := IsStation and ConnectOk and (PairUrl <> '');
end;

function ModeValue(Unused: String): String;
begin
  if IsStation then Result := 'estacao' else Result := 'principal';
end;

function NetworkValue(Unused: String): String;
begin
  if NetworkEnabled then Result := '1' else Result := '0';
end;

function ServerAddress(Unused: String): String;
begin
  Result := Trim(StationPage.Values[0]);
end;

function StorePort(Unused: String): String;
begin
  Result := Param('PORTA', PreviousValue('Porta', '8443'));
end;

function PairingAddress(Unused: String): String;
begin
  Result := PairUrl;
end;

{ Código de 13 a 40 letras e números (hífens e espaços são ignorados), como o servidor aceita. }
function CodeLooksValid(Code: String): Boolean;
var
  I, Count: Integer;
  C: Char;
begin
  Count := 0;
  Result := True;
  for I := 1 to Length(Code) do
  begin
    C := Code[I];
    if ((C >= '0') and (C <= '9')) or ((C >= 'A') and (C <= 'Z')) or ((C >= 'a') and (C <= 'z')) then
      Count := Count + 1
    else if (C <> '-') and (C <> ' ') then
      Result := False;
  end;
  Result := Result and (Count >= 13) and (Count <= 40);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := ((PageID = NetworkPage.ID) and IsStation) or ((PageID = StationPage.ID) and IsPrincipal) or
    ((PageID = ResultPage.ID) and (IsPrincipal or ConnectOk));
end;

{ "Conectar à loja": a CA só é instalada se a prova conferir com o código. O resultado (e a
  mensagem exata) vem do arquivo escrito pelo LocaControl.exe; sem ele, é falha. }
procedure RunConnect(Server, Code: String);
var
  ResultFile: String;
  Lines: TArrayOfString;
  Status: Integer;
begin
  ResultFile := ExpandConstant('{tmp}\conectar-resultado.txt');
  DeleteFile(ResultFile);
  PairUrl := '';
  Status := RunHidden(AppExe, 'conectar --servidor "' + Trim(Server) + '" --codigo "' + Trim(Code) +
    '" --porta ' + StorePort('') + ' --sem-navegador --resultado "' + ResultFile + '"');
  ConnectOk := False;
  if LoadStringsFromFile(ResultFile, Lines) and (GetArrayLength(Lines) >= 2) then
  begin
    { Pos: tolera um BOM UTF-8 lido como texto na primeira linha. }
    ConnectOk := (Status = 0) and (Pos('OK', Lines[0]) > 0) and (Pos('ERRO', Lines[0]) = 0);
    ConnectMessage := Lines[1];
    if ConnectOk and (GetArrayLength(Lines) >= 3) then
      PairUrl := Lines[2];
  end
  else
    ConnectMessage := 'O LocaControl não respondeu ao conectar (código ' + IntToStr(Status) + ').';
  Log('Conectar à loja: ' + ConnectMessage);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  { Em modo silencioso o Inno também chama esta função; recusar aqui repetiria a página para
    sempre. A falha da estação sai pelo código 20 (GetCustomSetupExitCode). }
  if WizardSilent then
    Exit;
  if (CurPageID = StationPage.ID) and ((ServerAddress('') = '') or not CodeLooksValid(StationPage.Values[1])) then
  begin
    MsgBox('Informe o endereço do computador principal e o código de pareamento completo ' +
      '(26 letras e números, como aparece no computador principal).', mbError, MB_OK);
    Result := False;
  end;
  if CurPageID = ResultPage.ID then
  begin
    if SkipConnect.Checked then
      Exit;
    if (Trim(ResultPage.Values[0]) = '') or not CodeLooksValid(ResultPage.Values[1]) then
    begin
      MsgBox('Informe o endereço e um código de pareamento novo, gerado agora no computador principal.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
    StationPage.Values[0] := Trim(ResultPage.Values[0]);
    RunConnect(ResultPage.Values[0], ResultPage.Values[1]);
    if not ConnectOk then
    begin
      ResultPage.SubCaptionLabel.Caption := ConnectMessage;
      MsgBox('Ainda não foi possível conectar. Nenhum certificado foi instalado.' + #13#10#13#10 +
        ConnectMessage, mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = ResultPage.ID then
  begin
    ResultPage.SubCaptionLabel.Caption := ConnectMessage + #13#10#13#10 +
      'Nenhum certificado foi instalado. Confira o endereço, gere um novo código no computador ' +
      'principal e tente de novo.';
    ResultPage.Values[0] := ServerAddress('');
    ResultPage.Values[1] := '';
  end;
  if (CurPageID = wpFinished) and IsStation then
  begin
    if ConnectOk then
      WizardForm.FinishedLabel.Caption :=
        'O certificado da loja foi conferido pelo código e instalado neste computador.' + #13#10#13#10 +
        'Falta um passo: no navegador, dê um nome a esta estação para concluir o pareamento. ' +
        'Até lá, este computador ainda não acessa a loja.'
    else
      WizardForm.FinishedLabel.Caption :=
        'Este computador NÃO está conectado à loja: nenhum certificado foi instalado.' + #13#10#13#10 +
        'Execute o instalador de novo com um código gerado no computador principal.';
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
  Path := DataDir + '\.env';
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

{ Permissões da pasta de dados por finalidade (SEC-P1E-01): SYSTEM e administradores com controle
  total; no principal, a identidade do serviço com modificação; nenhum acesso para os demais
  usuários (que usam o sistema pelo navegador). A lista inteira é substituída de uma vez
  (data-acl.ps1), o que também desfaz permissões acrescentadas por versões anteriores ou à mão. }
procedure ApplyDataAcl;
var
  Args: String;
begin
  ExtractTemporaryFile('data-acl.ps1');
  Args := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + ExpandConstant('{tmp}\data-acl.ps1') +
    '" -Data "' + DataDir + '"';
  if IsPrincipal then
    Args := Args + ' -Servico';
  if RunHidden(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Args) <> 0 then
  begin
    AclFailed := True;
    SuppressibleMsgBox('Não foi possível ajustar as permissões de ' + DataDir + '. Os dados podem ' +
      'estar acessíveis a outros usuários deste computador. Execute o instalador de novo.',
      mbError, MB_OK, IDOK);
  end;
end;

procedure ConfigureService;
var
  BinPath: String;
begin
  BinPath := 'binPath= "\"' + AppExe + '\" servico"';
  if Sc('query {#ServiceName}') <> 0 then
    Sc('create {#ServiceName} ' + BinPath + ' start= auto DisplayName= "LocaControl"');
  Sc('config {#ServiceName} ' + BinPath + ' start= auto obj= "{#ServiceAccount}"');
  Sc('description {#ServiceName} "Servidor do LocaControl. Dados em ' + DataDir + '."');
  { Reinício automático só em falha inesperada (não quando o banco é recusado na verificação). }
  Sc('failure {#ServiceName} reset= 86400 actions= restart/60000/restart/60000//');
  { Usuários interativos podem iniciar (o atalho sobe o servidor); só administradores param. }
  Sc('sdset {#ServiceName} D:(A;;CCLCSWRPWPDTLOCRRC;;;SY)(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;BA)(A;;CCLCSWRPLOCRRC;;;IU)(A;;CCLCSWLOCRRC;;;SU)');
end;

{ Encerramento controlado antes de trocar os arquivos (REL-P1E-02): sem forçar; se uma operação
  não terminar a tempo, a instalação é cancelada sem alterar nada. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Result := '';
  if FileExists(AppExe) then
  begin
    Code := RunHidden(AppExe, 'parar --sem-forcar --espera 600');
    if Code <> 0 then
      Result := 'O LocaControl em execução não terminou com segurança (backup ou gravação em andamento, ' +
        'código ' + IntToStr(Code) + '). Nada foi alterado. Tente a atualização de novo em alguns minutos.';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if IsPrincipal then
    begin
      SetEnv('LOCACONTROL_LOCAL_MODE', 'true');
      if NetworkEnabled then SetEnv('LOCACONTROL_NETWORK_MODE', 'true')
      else SetEnv('LOCACONTROL_NETWORK_MODE', 'false');
      ConfigureService;
      ApplyDataAcl;
      if Sc('start {#ServiceName}') <> 0 then
        Log('O serviço LocaControl não iniciou agora; ver ' + DataDir + '\logs\servidor.log');
    end
    else
    begin
      { Estação: sem servidor. Um principal convertido em estação deixa de ter o serviço. }
      ApplyDataAcl;
      Sc('stop {#ServiceName}');
      Sc('delete {#ServiceName}');
      RunConnect(ServerAddress(''), StationPage.Values[1]);
    end;
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := 0;
  if AclFailed then
    Result := EXIT_ACL_FAILED
  else if IsStation and not ConnectOk then
    Result := EXIT_NOT_CONNECTED;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
  begin
    if DirExists(DataDir) and
      (MsgBox('Os dados da loja (banco, contratos, documentos e backups) foram mantidos em ' + DataDir +
        '.' + #13#10#13#10 + 'Deseja EXCLUIR também esses dados? Isso não pode ser desfeito.',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) and
      (MsgBox('Confirme: excluir definitivamente todos os dados comerciais de ' + DataDir + '?',
        mbCriticalError, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
      DelTree(DataDir, True, True, True);
  end;
end;
