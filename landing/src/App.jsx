import { useState } from "react";
import IntroLoader from "./components/IntroLoader.jsx";
import TickerTape from "./components/TickerTape.jsx";
import Nav from "./components/Nav.jsx";
import Hero from "./sections/Hero.jsx";
import LaptopReveal from "./components/LaptopReveal.jsx";
import InfluencePillar from "./sections/InfluencePillar.jsx";
import QuantSection from "./sections/QuantSection.jsx";
import Supporting from "./sections/Supporting.jsx";
import Pricing from "./sections/Pricing.jsx";
import FinalCTA from "./sections/FinalCTA.jsx";
import Footer from "./sections/Footer.jsx";
import SignIn from "./components/SignIn.jsx";

export default function App() {
  const [intro, setIntro] = useState(true);
  const [signInOpen, setSignInOpen] = useState(false);
  const openSignIn = () => setSignInOpen(true);

  return (
    <>
      {/* Intro loader slides up to reveal the site, which loads underneath (item 4). */}
      {intro ? <IntroLoader onDone={() => setIntro(false)} /> : null}

      <TickerTape />
      <Nav onSignIn={openSignIn} />
      <main>
        {/* the single interactive influence map lives in the hero (item 1) */}
        <Hero onSignIn={openSignIn} />

        {/* Apple-style laptop scroll reveal of the real dashboard (item 3) */}
        <LaptopReveal />

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
