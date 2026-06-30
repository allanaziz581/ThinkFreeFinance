import Nav from "./components/Nav.jsx";
import Hero from "./sections/Hero.jsx";
import InfluencePillar from "./sections/InfluencePillar.jsx";
import QuantSection from "./sections/QuantSection.jsx";
import Supporting from "./sections/Supporting.jsx";
import FinalCTA from "./sections/FinalCTA.jsx";
import Footer from "./sections/Footer.jsx";

export default function App() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <InfluencePillar />
        <QuantSection />
        <Supporting />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
