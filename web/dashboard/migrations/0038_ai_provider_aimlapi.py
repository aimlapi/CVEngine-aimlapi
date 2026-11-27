from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0037_drop_unused_legacy_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aiprovidersettings',
            name='provider',
            field=models.CharField(choices=[('anthropic', 'Anthropic'), ('openai', 'OpenAI'), ('openrouter', 'OpenRouter'), ('aimlapi', 'AI/ML API'), ('ollama', 'Ollama'), ('vllm', 'vLLM'), ('lmstudio', 'LM Studio')], default='anthropic', max_length=32),
        ),
    ]
