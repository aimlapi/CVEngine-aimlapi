"""The AI/ML API provider (reNgine/ai_providers.AIMLAPIProvider): an OpenAI-compatible hosted API whose key is only ever sent to
https://api.aimlapi.com, whose model list is cut down to the models served on chat/completions, and which leaves every other provider and
the stored default as they were. No request leaves the machine (``requests`` is replaced)."""
import unittest
from unittest import mock

from reNgine import ai_profiles, ai_providers as ai

CATALOG = {'object': 'list', 'data': [
	{'id': 'openai/gpt-5.4-nano', 'type': 'openai/chat-completions', 'info': {'releasedAt': '2026-03-05'},
	 'pricing': {'units': [{'name': 'token', 'origin': 'provided', 'phase': 'inference', 'measure': 'input', 'price': 0.21, 'per': 1000000}]}},
	{'id': 'anthropic/claude-haiku-5.5', 'type': 'openai/chat-completions', 'info': {'releasedAt': '2026-10-07'}},
	{'id': 'anthropic/claude-haiku-5.5', 'type': 'anthropic/messages', 'info': {'releasedAt': '2026-10-07'}},
	{'id': 'flux/schnell', 'type': 'openai/images-generations', 'info': {'releasedAt': '2026-11-01'}},
	{'id': 'text-embedding-3-small', 'type': 'openai/embeddings', 'info': {'releasedAt': '2026-11-02'}},
]}


class Resp:
	def __init__(self, data, status=200, headers=None):
		self._data, self.status_code, self.headers = data, status, headers or {}

	def raise_for_status(self):
		pass

	def json(self):
		return self._data


def reply(text='ok'):
	return Resp({'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 3, 'completion_tokens': 1}})


class AIMLAPIProfileTests(unittest.TestCase):
	def test_it_is_a_named_hosted_provider_with_its_own_address_and_a_fallback_model(self):
		profile = ai_profiles.PROFILES['aimlapi']
		self.assertEqual((profile.label, profile.transport, profile.default_base), ('AI/ML API', 'openai_chat', 'https://api.aimlapi.com/v1'))
		self.assertTrue(profile.needs_key)
		self.assertFalse(profile.needs_url)
		self.assertIn('aimlapi', ai.PROVIDERS)
		self.assertNotIn('aimlapi', ai.KEYLESS)
		self.assertNotIn('aimlapi', ai.SELECTABLE)  # with no model chosen it picks one, like Anthropic and OpenAI
		self.assertEqual(ai.DEFAULT_MODELS['aimlapi'], 'openai/gpt-5.4-nano')
		with self.assertRaises(ai.AIProviderError):
			ai.get_provider('aimlapi')
		self.assertIsNone(ai.detect_provider('sk-0123456789abcdef'))  # a bare sk- key is never guessed onto it
		self.assertTrue(ai.ambiguous_key('sk-0123456789abcdef'))

	def test_it_is_a_choice_in_the_settings_model_and_the_stored_default_is_unchanged(self):
		from dashboard.models import AIProviderSettings
		field = AIProviderSettings._meta.get_field('provider')
		self.assertIn(('aimlapi', 'AI/ML API'), field.choices)
		self.assertEqual(field.default, 'anthropic')

class AIMLAPIRequestTests(unittest.TestCase):
	def setUp(self):
		ai._RESOLVED.clear()

	def test_a_completion_goes_to_its_chat_endpoint_with_the_key_as_a_bearer_header(self):
		with mock.patch('requests.post', return_value=reply()) as post:
			self.assertEqual(ai.get_provider('aimlapi', api_key='test-key', model='openai/gpt-5.4-nano').complete('s', 'u'), 'ok')
		self.assertEqual(post.call_args.args[0], 'https://api.aimlapi.com/v1/chat/completions')
		self.assertEqual(post.call_args.kwargs['headers'], {'Authorization': 'Bearer test-key'})
		self.assertEqual(post.call_args.kwargs['json']['model'], 'openai/gpt-5.4-nano')
		self.assertNotIn('HTTP-Referer', post.call_args.kwargs['headers'])  # OpenRouter's attribution headers are its own

	def test_the_key_goes_only_to_the_exact_host_over_https(self):
		for base in ('https://api.aimlapi.com.evil.example/v1', 'https://evil.example/v1', 'http://api.aimlapi.com/v1',
					 'https://aimlapi.com/v1', 'https://xapi.aimlapi.com/v1', 'https://api.aimlapi.com@evil.example/v1'):
			with mock.patch('requests.post', return_value=reply()) as post, mock.patch('reNgine.ai_providers._redirect_refused', return_value=False):
				ai.get_provider('aimlapi', api_key='test-key', model='m', base_url=base).complete('s', 'u')
			self.assertEqual(post.call_args.kwargs['headers'], {}, base)
		with mock.patch('requests.post', return_value=reply()) as post:
			ai.get_provider('aimlapi', api_key='test-key', model='m', base_url='https://API.aimlapi.com/v1/').complete('s', 'u')
		self.assertEqual(post.call_args.kwargs['headers'], {'Authorization': 'Bearer test-key'})
		# the other providers send what they sent before: OpenAI's key still goes to the gateway its Base URL names
		with mock.patch('requests.post', return_value=reply()) as post:
			ai.get_provider('openai', api_key='k', model='m', base_url='https://gateway.example/v1').complete('s', 'u')
		self.assertEqual(post.call_args.kwargs['headers'], {'Authorization': 'Bearer k'})

	def test_a_redirect_to_another_host_does_not_carry_the_key(self):
		with mock.patch('requests.get') as get, mock.patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 0))]):
			get.side_effect = [Resp({}, 302, {'Location': 'https://cdn.example.com/v1/models'}), Resp(CATALOG)]
			ai.get_provider('aimlapi', api_key='test-key').list_models()
		first, second = get.call_args_list
		self.assertEqual(first.args[0], 'https://api.aimlapi.com/v1/models')
		self.assertEqual(first.kwargs['headers'], {'Authorization': 'Bearer test-key'})
		self.assertEqual(second.args[0], 'https://cdn.example.com/v1/models')
		self.assertEqual(second.kwargs['headers'], {})

	def test_the_model_list_holds_only_chat_models_newest_first_with_their_price(self):
		with mock.patch('requests.get', return_value=Resp(CATALOG)):
			models = ai.get_provider('aimlapi', api_key='test-key').list_models()
		self.assertEqual([m['id'] for m in models], ['anthropic/claude-haiku-5.5', 'openai/gpt-5.4-nano'])
		self.assertGreater(models[0]['created'], models[1]['created'])
		self.assertAlmostEqual(models[1]['price'], 0.21)
		self.assertIsNone(models[0]['price'])

	def test_with_no_model_chosen_the_newest_cheapest_chat_model_is_used_else_the_fallback(self):
		with mock.patch('requests.get', return_value=Resp(CATALOG)):
			self.assertEqual(ai.get_provider('aimlapi', api_key='test-key').default_model(), 'anthropic/claude-haiku-5.5')
		ai._RESOLVED.clear()
		with mock.patch('requests.get', side_effect=ai.requests.ConnectionError('down')):
			self.assertEqual(ai.get_provider('aimlapi', api_key='test-key').default_model(), 'openai/gpt-5.4-nano')
