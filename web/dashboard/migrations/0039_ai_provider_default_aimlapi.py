from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0038_ai_provider_aimlapi'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aiprovidersettings',
            name='provider',
            field=models.CharField(choices=[('anthropic', 'Anthropic'), ('openai', 'OpenAI'), ('openrouter', 'OpenRouter'), ('aimlapi', 'AI/ML API'), ('ollama', 'Ollama'), ('vllm', 'vLLM'), ('lmstudio', 'LM Studio')], default='aimlapi', max_length=32),
        ),
    ]
