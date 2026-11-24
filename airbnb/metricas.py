class Metricas:
    """Contadores de uma execução. Cada execução recebe um objeto novo,
    não há contador global.

    comparacoes: comparações entre chaves (ordenação, busca e hash)
    movimentacoes: escritas de elementos em uma lista durante a ordenação
    passos: iterações do laço principal da busca (sondagens na interpolação,
            divisões na binária, posições visitadas na sequencial)
    colisoes: inserções na hash que caíram em balde não vazio
    """

    def __init__(self):
        self.comparacoes = 0
        self.movimentacoes = 0
        self.passos = 0
        self.colisoes = 0

    def como_dict(self) -> dict:
        return {"comparacoes": self.comparacoes, "movimentacoes": self.movimentacoes,
                "passos": self.passos, "colisoes": self.colisoes}

    def __repr__(self):
        return f"Metricas({self.como_dict()})"
