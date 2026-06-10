import Layout from "@theme/Layout";

import { HeroSection } from "./_sections/HeroSection/HeroSection";
import { KeyCapabilities } from "./_sections/KeyCapabilities/KeyCapabilities";
import { PolicyExecution } from "./_sections/PolicyExecution/PolicyExecution";

export default function Home() {
  return (
    <Layout description="Physical AI Framework is a production-ready runtime that executes AI policies on physical systems">
      <HeroSection />
      <PolicyExecution />
      <KeyCapabilities />
    </Layout>
  );
}
