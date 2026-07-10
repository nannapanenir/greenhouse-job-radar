/**
 * Vercel Serverless Function
 * Returns Greenhouse company configuration from the GREENHOUSE_COMPANIES
 * environment variable. Company configuration stays server-controlled and
 * is never exposed directly to the client.
 */

function json(statusCode, body) {
  return new Response(JSON.stringify(body), {
    status: statusCode,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}

function validateCompany(company) {
  return (
    company &&
    typeof company === 'object' &&
    typeof company.name === 'string' && company.name.trim() !== '' &&
    typeof company.token === 'string' && company.token.trim() !== '' &&
    typeof company.enabled === 'boolean'
  );
}

export default async function handler() {
  const raw = process.env.GREENHOUSE_COMPANIES;

  if (!raw) {
    return json(500, {
      error: 'GREENHOUSE_COMPANIES configuration is missing',
    });
  }

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return json(500, {
      error: 'Invalid GREENHOUSE_COMPANIES configuration',
    });
  }

  if (!Array.isArray(parsed)) {
    return json(500, {
      error: 'Invalid GREENHOUSE_COMPANIES configuration',
    });
  }

  const companies = parsed
    .filter(validateCompany)
    .map(company => ({
      name: company.name,
      token: company.token,
      enabled: company.enabled,
    }));

  return json(200, { companies });
}
