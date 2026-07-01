import { useState } from "react";
import Nav from "./components/Nav.jsx";
import Hero from "./sections/Hero.jsx";
import ContainerScroll from "./components/ContainerScroll.jsx";
import DashboardMock from "./components/DashboardMock.jsx";
import InfluencePillar from "./sections/InfluencePillar.jsx";
import QuantSection from "./sections/QuantSection.jsx";
import Supporting from "./sections/Supporting.jsx";
import Pricing from "./sections/Pricing.jsx";
import FinalCTA from "./sections/FinalCTA.jsx";
import Footer from "./sections/Footer.jsx";
import SignIn from "./components/SignIn.jsx";

export default function App() {
  const [signInOpen, setSignInOpen] = useState(false);
  const openSignIn = () => setSignInOpen(true);

  return (
    <>
      <Nav onSignIn={openSignIn} />
      <main>
        {/* the single influence map lives in the hero */}
        <Hero onSignIn={openSignIn} />

        {/* distinct visual: the intelligence dashboard reveals on scroll */}
        <ContainerScroll
          kicker="The product"
          title="Your intelligence dashboard, in one view"
        >
          <DashboardMock />
        </ContainerScroll>

        <InfluencePillar />
        <QuantSection />
        <Supporting />
        <Pricing />
        <FinalCTA onSignIn={openSignIn} />
      </main>
      <Footer />

      <SignIn open={signInOpen} onClose={() => setSignInOpen(false)} />
    </>
  );
}
