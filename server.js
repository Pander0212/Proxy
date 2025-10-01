const express = require('express');
const cors = require('cors');
const axios = require('axios');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

const NIM_API_BASE = process.env.NIM_API_BASE || 'https://integrate.api.nvidia.com/v1';
const NIM_API_KEY = process.env.NIM_API_KEY;

// Aliases → NIM model IDs.
// If a client passes a full NIM ID (contains "/"), it will be used as-is.
const MODEL_MAPPING = {
  // OpenAI-style aliases → Llama 3.1 on NIM
  'gpt-3.5-turbo': 'meta/llama-3.1-8b-instruct',
  'gpt-4': 'meta/llama-3.1-70b-instruct',
  'gpt-4-turbo': 'meta/llama-3.1-405b-instruct',

  // Llama 3.1 pass-through aliases
  'llama-3.1-8b-instruct': 'meta/llama-3.1-8b-instruct',
  'llama-3.1-70b-instruct': 'meta/llama-3.1-70b-instruct',
  'llama-3.1-405b-instruct': 'meta/llama-3.1-405b-instruct',

  // DeepSeek V3.1 and R1 (NIM catalog)
  // Note: v3.1 model slug on build.nvidia.com uses underscore in the path.
  'deepseek-v3.1': 'deepseek-ai/deepseek-v3_1',
  'deepseek-v3.1-instruct': 'deepseek-ai/deepseek-v3_1',
  'deepseek-v3_1': 'deepseek-ai/deepseek-v3_1',
  'deepseek-r1': 'deepseek-ai/deepseek-r1',
  // Common specific build ID seen in examples/catalogs
  'deepseek-r1-0528': 'deepseek-ai/deepseek-r1-0528',

  // Mixtral / Mistral
  'mixtral-8x7b-instruct': 'mistralai/mixtral-8x7b-instruct-v0.1',
  'mistral-7b-instruct': 'mistralai/mistral-7b-instruct',

  // Gemma
  'gemma-2-9b-it': 'google/gemma-2-9b-it',
  'gemma-2-27b-it': 'google/gemma-2-27b-it',

  // Qwen (illustrative common aliases)
  'qwen2.5-72b-instruct': 'qwen/qwen2.5-72b-instruct',
  'qwen2.5-14b-instruct': 'qwen/qwen2.5-14b-instruct'
};

// Default model if none/unknown provided
const DEFAULT_MODEL = MODEL_MAPPING['gpt-3.5-turbo'];

// Resolve model: full NIM IDs pass through, otherwise map aliases
function resolveModel(input) {
  if (!input) return DEFAULT_MODEL;
  if (input.includes('/')) return input; // already a NIM model id
  return MODEL_MAPPING[input] || DEFAULT_MODEL;
}

// Accept API key from Authorization header (Bearer nvapi-xxx) or env
function getNimApiKey(req) {
  const auth = req.headers['authorization'] || '';
  if (auth.startsWith('Bearer ')) return auth.slice(7);
  return NIM_API_KEY || '';
}

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'OpenAI to NVIDIA NIM Proxy' });
});

app.get('/v1/models', (req, res) => {
  // Present the alias list as OpenAI-style models for client UIs
  const models = Object.keys(MODEL_MAPPING).map(model => ({
    id: model,
    object: 'model',
    created: Date.now(),
    owned_by: 'nvidia-nim-proxy'
  }));

  res.json({
    object: 'list',
     models
  });
});

app.post('/v1/chat/completions', async (req, res) => {
  try {
    const { model, messages, temperature, max_tokens, top_p, stream } = req.body;

    const nimModel = resolveModel(model);
    const nimRequest = {
      model: nimModel,
      messages,
      temperature: typeof temperature === 'number' ? temperature : 0.7,
      top_p: typeof top_p === 'number' ? top_p : 1.0,
      max_tokens: typeof max_tokens === 'number' ? max_tokens : 1024,
      stream: !!stream
    };

    const apiKey = getNimApiKey(req);
    if (!apiKey) {
      return res.status(401).json({
        error: { message: 'Missing NVIDIA API key', type: 'invalid_request_error', code: 401 }
      });
    }

    const response = await axios.post(`${NIM_API_BASE}/chat/completions`, nimRequest, {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      responseType: stream ? 'stream' : 'json'
    });

    if (stream) {
      // Pass through SSE stream
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      response.data.pipe(res);
    } else {
      // Return OpenAI-style response
      const openaiResponse = {
        id: `chatcmpl-${Date.now()}`,
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: model || nimModel,
        choices: (response.data.choices || []).map(choice => ({
          index: choice.index,
          message: choice.message,
          finish_reason: choice.finish_reason
        })),
        usage: response.data.usage || {
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0
        }
      };

      res.json(openaiResponse);
    }
  } catch (error) {
    console.error('Proxy error:', error?.response?.data || error.message);
    res.status(error.response?.status || 500).json({
      error: {
        message: error.response?.data?.error?.message || error.message || 'Internal server error',
        type: 'invalid_request_error',
        code: error.response?.status || 500
      }
    });
  }
});

app.all('*', (req, res) => {
  res.status(404).json({
    error: {
      message: `Endpoint ${req.path} not found`,
      type: 'invalid_request_error',
      code: 404
    }
  });
});

app.listen(PORT, () => {
  console.log(`OpenAI to NVIDIA NIM Proxy running on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
});
