# Simulador de dispositivos

Cliente Python com biblioteca padrão para exercitar a API do Access Gateway. Requer Python 3.9+ e o backend em execução, com acesso ao PostgreSQL.

## Preparação

O simulador usa um dispositivo já cadastrado. A chave dele aparece somente na resposta de `POST /devices` ou de `POST /devices/{id}/credentials`; uma consulta posterior não a recupera. Para cadastrar um dispositivo de demonstração no PowerShell, com `ACCESS_GATEWAY_ADMIN_TOKEN` já definido no ambiente:

```powershell
$registration = Invoke-RestMethod -Method Post -Uri 'http://localhost:8080/devices' `
  -Headers @{ Authorization = "Bearer $env:ACCESS_GATEWAY_ADMIN_TOKEN" } `
  -ContentType 'application/json' `
  -Body '{"serialNumber":"ACCESS-001","name":"Simulador"}'
$env:ACCESS_GATEWAY_DEVICE_ID = $registration.device.id
$env:ACCESS_GATEWAY_DEVICE_KEY = $registration.apiKey
```

Cadastre uma referência e atribua-a ao dispositivo antes de enviar eventos. Use um valor de demonstração exclusivo para cada execução:

```powershell
$env:ACCESS_GATEWAY_CREDENTIAL_REF = 'SIM-' + [guid]::NewGuid().ToString('N')
$headers = @{ Authorization = "Bearer $env:ACCESS_GATEWAY_ADMIN_TOKEN" }
$body = @{ credentialRef = $env:ACCESS_GATEWAY_CREDENTIAL_REF } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://localhost:8080/credential-refs' -Headers $headers -ContentType 'application/json' -Body $body
Invoke-RestMethod -Method Post -Uri "http://localhost:8080/devices/$env:ACCESS_GATEWAY_DEVICE_ID/credential-refs" -Headers $headers -ContentType 'application/json' -Body $body
```

Se já existe um dispositivo, configure `ACCESS_GATEWAY_DEVICE_ID` com seu UUID e `ACCESS_GATEWAY_DEVICE_KEY` com sua chave. No modo anterior, `ACCESS_GATEWAY_ADMIN_TOKEN` permite consultar o histórico. No modo OIDC, defina `ACCESS_GATEWAY_ADMIN_BEARER` com um token de acesso do Keycloak que tenha o papel `access-admin` e a audiência `access-gateway`. Esse token tem validade curta; obtenha-o por um fluxo de login autorizado. Para exercitar apenas o envio do dispositivo, use `--skip-history` sem credencial administrativa. Não coloque credenciais em arquivos versionados nem em argumentos de linha de comando.

## Execução

Execute a partir deste repositório:

```powershell
python main.py --scenario valid
python main.py --scenario duplicate
python main.py --scenario invalid
python main.py --scenario invalid-key
python main.py --scenario valid --skip-history
```

Use `--base-url http://host:porta` se o backend não estiver em `http://localhost:8080`.

| Cenário | Envio esperado | Registros para o ID desta execução |
| --- | --- | ---: |
| `valid` | 201 Created | 1 |
| `duplicate` | 201 Created, depois 200 OK com o mesmo ID | 1 |
| `invalid` | 400 Bad Request; campo `occurredAt` ausente | 0 |
| `invalid-key` | 401 Unauthorized; Bearer inválido | 0 |

Exemplo ilustrativo, não uma execução já realizada:

```text
[SIMULATOR] Device: <uuid-do-dispositivo>

[1] Sending event EVT-...
    HTTP 201 - CREATED

[2] Resending event EVT-...
    HTTP 200 - DUPLICATE

[3] Querying event history
    Persisted records: 1

[RESULT] PASS
```

O simulador gera um `externalEventId` novo em cada execução e usa a `ACCESS_GATEWAY_CREDENTIAL_REF` cadastrada e atribuída ao dispositivo. A contagem de registros é filtrada pelo `externalEventId` enviado. O histórico da API é limitado aos 100 eventos mais recentes por `occurredAt`; se o dispositivo já tiver mais de 100 eventos com horários posteriores ao evento enviado, a verificação pode falhar mesmo com a gravação correta. Nesse caso, use um dispositivo de demonstração com histórico adequado. O programa sai com código `0` em caso de sucesso e `1` em caso de falha.

## Testes locais

Os testes usam um servidor HTTP local simulado e não precisam do backend:

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

## Padrão de documentação e configuração

Este repositório existe para simular dispositivos e eventos para validação do Access Gateway. O README acima apresenta o escopo, a arquitetura e as tecnologias específicas do projeto; esta seção padroniza o ponto de entrada para quem deseja reproduzi-lo localmente.

### Clonar e configurar

~~~powershell
git clone https://github.com/Ivictors/device-simulator.git
cd device-simulator
~~~

Consulte os pré-requisitos e comandos de execução descritos neste README antes de iniciar. Use variáveis de ambiente, arquivos locais ignorados pelo Git e serviços de desenvolvimento para credenciais; não substitua placeholders por segredos no README e não versione chaves, tokens ou senhas.
