from django import forms

from .models import Consumivel, Impressora, ModeloImpressora


def _recusar_nome_repetido(modelo, nome, mensagem, exceto=None):
    """Nome igual a outro já cadastrado (sem diferenciar maiúsculas) confunde as telas e os pedidos."""
    outros = modelo.objects.filter(nome__iexact=nome.strip())
    if exceto is not None:
        outros = outros.exclude(pk=exceto)
    if outros.exists():
        raise forms.ValidationError(mensagem)
    return nome.strip()


class ImpressoraForm(forms.ModelForm):
    class Meta:
        model = Impressora
        fields = ['nome', 'modelo', 'numero_serie', 'localizacao']


class ModeloNovoForm(forms.Form):
    """Cria o modelo e, de uma vez, os toners de cada cor e a caixa de resíduo."""
    TIPOS = [('colorida', 'Colorida (preto, ciano, magenta e amarelo)'),
             ('mono', 'Preto e branco (só preto)')]
    nome = forms.CharField(max_length=100)
    tipo = forms.ChoiceField(choices=TIPOS)
    usa_residuo = forms.BooleanField(required=False)
    estoque_minimo = forms.IntegerField(min_value=0, initial=2)

    def clean_nome(self):
        return _recusar_nome_repetido(ModeloImpressora, self.cleaned_data['nome'],
                                      'Já existe um modelo com esse nome.')


class ModeloNomeForm(forms.ModelForm):
    class Meta:
        model = ModeloImpressora
        fields = ['nome']

    def clean_nome(self):
        return _recusar_nome_repetido(ModeloImpressora, self.cleaned_data['nome'],
                                      'Já existe um modelo com esse nome.', exceto=self.instance.pk)


class ConsumivelNovoForm(forms.ModelForm):
    class Meta:
        model = Consumivel
        fields = ['nome', 'tipo', 'estoque_unidade', 'estoque_minimo']

    def clean_nome(self):
        return _recusar_nome_repetido(Consumivel, self.cleaned_data['nome'],
                                      'Já existe um item com esse nome.')


class ConsumivelEditarForm(forms.ModelForm):
    # fora de Meta.fields: o estoque não é gravado pelo formulário, e sim por ajustar_estoque,
    # que registra a mudança no histórico
    estoque_unidade = forms.IntegerField(min_value=0, label='Em estoque')

    class Meta:
        model = Consumivel
        fields = ['nome', 'estoque_minimo']

    def clean_nome(self):
        return _recusar_nome_repetido(Consumivel, self.cleaned_data['nome'],
                                      'Já existe um item com esse nome.', exceto=self.instance.pk)
