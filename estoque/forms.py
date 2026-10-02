from django import forms

from .models import Consumivel, Impressora, ModeloImpressora


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


class ModeloNomeForm(forms.ModelForm):
    class Meta:
        model = ModeloImpressora
        fields = ['nome']


class ConsumivelNovoForm(forms.ModelForm):
    class Meta:
        model = Consumivel
        fields = ['nome', 'tipo', 'estoque_unidade', 'estoque_minimo']


class ConsumivelEditarForm(forms.ModelForm):
    class Meta:
        model = Consumivel
        fields = ['nome', 'estoque_unidade', 'estoque_minimo']
