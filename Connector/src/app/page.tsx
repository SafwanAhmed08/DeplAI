'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';

import Threads from '@/components/background-animation';
import LogoLoop from '@/components/logo-loop';
import ShinyText from '@/components/shiny-text';
import { SiGithub, SiNextdotjs, SiDocker, SiLangchain, SiPrisma, SiTailwindcss } from 'react-icons/si';

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      const res = await fetch('/api/auth/session');
      const session = await res.json();

      if (session.isLoggedIn) {
        router.push('/dashboard');
        return;
      }

      setLoading(false);
    } catch (error) {
      console.error('Auth check failed:', error);
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black relative">
      {/* Threads Background */}
      <div className="absolute inset-0 z-0">
        <Threads
          color={[1, 1, 1]}
          amplitude={1}
          distance={0}
          enableMouseInteraction
        />
      </div>

      {/* Navigation */}
      <motion.nav
        className="container mx-auto px-6 py-6 relative z-10"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-white text-2xl font-bold">DEPLAI</span>
          </div>
          <Link
            href="/api/auth/login"
            className="text-white text-lg font-bold transition-all duration-300 hover:scale-105"
          >
            <ShinyText
              text="Continue with GitHub"
              speed={2}
              color="#b5b5b5"
              shineColor="#ffffff"
              spread={120}
              direction="left"
            />
          </Link>
        </div>
      </motion.nav>

      {/* Hero Section */}
      <div className="container mx-auto px-6 py-20 relative z-10">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <motion.div
            className="inline-flex items-center space-x-2 bg-blue-500/10 border border-blue-500/20 rounded-full px-4 py-2 mb-8"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
            <span className="text-white text-sm">AI-Powered Platform</span>
          </motion.div>

          {/* Headline with staggered animation */}
          <h1 className="text-6xl md:text-7xl font-bold text-white mb-6 leading-tight">
            <motion.div
              initial={{ opacity: 0, x: -50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
            >
              Deploy Anywhere
            </motion.div>
            <motion.span
              className="text-white inline-block"
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
            >
              Test Everything
            </motion.span>
          </h1>

        </div>
      </div>

      {/* Logo Loop */}
      <div className="absolute bottom-32 left-0 right-0 z-10 flex justify-center">
        <div className="max-w-[850px] w-full h-[120px] overflow-hidden text-white">
          <LogoLoop
            logos={[
              { node: <SiGithub />, title: "GitHub" },
              { node: <SiLangchain />, title: "LangGraph" },
              { node: <SiNextdotjs />, title: "Next.js" },
              { node: <SiDocker />, title: "Docker" },
              { node: <SiPrisma />, title: "Prisma" },
              { node: <svg fill="currentColor" fillRule="evenodd" height="1em" width="1em" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M4.709 15.955l4.72-2.647.08-.23-.08-.128H9.2l-.79-.048-2.698-.073-2.339-.097-2.266-.122-.571-.121L0 11.784l.055-.352.48-.321.686.06 1.52.103 2.278.158 1.652.097 2.449.255h.389l.055-.157-.134-.098-.103-.097-2.358-1.596-2.552-1.688-1.336-.972-.724-.491-.364-.462-.158-1.008.656-.722.881.06.225.061.893.686 1.908 1.476 2.491 1.833.365.304.145-.103.019-.073-.164-.274-1.355-2.446-1.446-2.49-.644-1.032-.17-.619a2.97 2.97 0 01-.104-.729L6.283.134 6.696 0l.996.134.42.364.62 1.414 1.002 2.229 1.555 3.03.456.898.243.832.091.255h.158V9.01l.128-1.706.237-2.095.23-2.695.08-.76.376-.91.747-.492.584.28.48.685-.067.444-.286 1.851-.559 2.903-.364 1.942h.212l.243-.242.985-1.306 1.652-2.064.73-.82.85-.904.547-.431h1.033l.76 1.129-.34 1.166-1.064 1.347-.881 1.142-1.264 1.7-.79 1.36.073.11.188-.02 2.856-.606 1.543-.28 1.841-.315.833.388.091.395-.328.807-1.969.486-2.309.462-3.439.813-.042.03.049.061 1.549.146.662.036h1.622l3.02.225.79.522.474.638-.079.485-1.215.62-1.64-.389-3.829-.91-1.312-.329h-.182v.11l1.093 1.068 2.006 1.81 2.509 2.33.127.578-.322.455-.34-.049-2.205-1.657-.851-.747-1.926-1.62h-.128v.17l.444.649 2.345 3.521.122 1.08-.17.353-.608.213-.668-.122-1.374-1.925-1.415-2.167-1.143-1.943-.14.08-.674 7.254-.316.37-.729.28-.607-.461-.322-.747.322-1.476.389-1.924.315-1.53.286-1.9.17-.632-.012-.042-.14.018-1.434 1.967-2.18 2.945-1.726 1.845-.414.164-.717-.37.067-.662.401-.589 2.388-3.036 1.44-1.882.93-1.086-.006-.158h-.055L4.132 18.56l-1.13.146-.487-.456.061-.746.231-.243 1.908-1.312-.006.006z"/></svg>, title: "Claude" },
              { node: <SiTailwindcss />, title: "Tailwind CSS" },
            ]}
            speed={60}
            direction="left"
            logoHeight={55}
            gap={60}
            hoverSpeed={0}
            fadeOut
            fadeOutColor="#000000"
            ariaLabel="Technology partners"
          />
        </div>
      </div>

      {/* Footer */}
      <motion.footer
        className="container mx-auto px-6 py-8 border-t border-white/10 absolute bottom-0 left-0 right-0 z-10"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 1 }}
      >
        <div className="text-center">
          <div className="text-gray-400 text-sm">
             Built for developers, by developers.
          </div>
        </div>
      </motion.footer>
    </div>
  );
}
