export default function handler(req, res) {
  try {
    if (req.method !== "GET") {
      return res.status(405).json({
        error: "Method not allowed"
      });
    }

    const rawCompanies = process.env.GREENHOUSE_COMPANIES;

    if (!rawCompanies) {
      return res.status(500).json({
        error: "GREENHOUSE_COMPANIES configuration is missing"
      });
    }

    const parsedCompanies = JSON.parse(rawCompanies);

    if (!Array.isArray(parsedCompanies)) {
      return res.status(500).json({
        error: "Invalid GREENHOUSE_COMPANIES configuration"
      });
    }

    const companies = parsedCompanies
      .filter((company) => {
        return (
          company &&
          typeof company.name === "string" &&
          company.name.trim() !== "" &&
          typeof company.token === "string" &&
          company.token.trim() !== "" &&
          typeof company.enabled === "boolean"
        );
      })
      .map((company) => ({
        name: company.name.trim(),
        token: company.token.trim(),
        enabled: company.enabled
      }));

    res.setHeader(
      "Cache-Control",
      "public, s-maxage=3600, stale-while-revalidate=86400"
    );

    return res.status(200).json({
      companies
    });
  } catch (error) {
    console.error("Company configuration parsing failed:", error.message);

    return res.status(500).json({
      error: "Invalid GREENHOUSE_COMPANIES configuration"
    });
  }
}
