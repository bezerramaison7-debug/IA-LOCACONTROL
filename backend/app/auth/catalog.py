"""Only implemented capabilities. Business permissions will arrive with each module."""

PERMISSIONS = {
    "imports.read": "Consultar importações e arquivos enviados",
    "imports.write": "Enviar Excel, validar e confirmar importações",
    "workspace.view": "Acessar a prévia dos módulos internos (sem dados comerciais reais)",
    "users.read": "Consultar usuários",
    "users.write": "Criar, editar, desativar usuários e redefinir senhas",
    "roles.read": "Consultar perfis e permissões",
    "roles.write": "Alterar permissões dos perfis internos",
    "audit.read": "Consultar auditoria de segurança",
    "customers.read": "Consultar clientes",
    "customers.write": "Cadastrar, editar e desativar clientes",
    "products.read": "Consultar produtos",
    "products.write": "Cadastrar, editar e desativar produtos",
    "equipment.read": "Consultar equipamentos",
    "equipment.write": "Cadastrar e editar equipamentos",
    "stock.read": "Consultar estoque e movimentos",
    "stock.write": "Movimentar estoque e situação de equipamentos",
    "prices.read": "Consultar preços e histórico",
    "prices.write": "Publicar, revisar e desativar preços",
}
ROLES = {
    "ADMINISTRADOR": "Administrador",
    "COMERCIAL": "Comercial",
    "OPERACAO": "Operação",
    "FINANCEIRO": "Financeiro",
    "CLIENTE": "Cliente",
}


def permission_codes(user):
    return sorted({p.code for role in user.roles for p in role.permissions})
