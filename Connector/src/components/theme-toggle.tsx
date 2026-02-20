'use client';

import { useEffect, useState } from 'react';

export default function ThemeToggle() {
  const [isDark, setIsDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Check localStorage and system preference
    const storedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (storedTheme === 'dark') {
      setIsDark(true);
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else {
      setIsDark(false);
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
    }
  }, []);

  const toggleTheme = () => {
    if (isDark) {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
      localStorage.setItem('theme', 'light');
      setIsDark(false);
    } else {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
      localStorage.setItem('theme', 'dark');
      setIsDark(true);
    }
  };

  // Prevent hydration mismatch
  if (!mounted) {
    return (
      <button className="p-2 rounded-lg transition opacity-0">
        <div className="w-6 h-6" />
      </button>
    );
  }

  return (
    <button
      onClick={toggleTheme}
      className="p-2 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-[#1a1a1a] rounded-lg transition"
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? (
        // Light mode icon (sun/monitor for light)
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M4.25 4.17188C3.00736 4.17188 2 5.17923 2 6.42187V13.8281C2 15.0708 3.00736 16.0781 4.25 16.0781H11.25H12.75H19.75C20.9926 16.0781 22 15.0708 22 13.8281V6.42188C22 5.17923 20.9926 4.17188 19.75 4.17188H4.25ZM3.5 6.42187C3.5 6.00766 3.83579 5.67188 4.25 5.67188H19.75C20.1642 5.67188 20.5 6.00766 20.5 6.42188V13.8281C20.5 14.2423 20.1642 14.5781 19.75 14.5781H4.25C3.83579 14.5781 3.5 14.2423 3.5 13.8281V6.42187Z" fill="currentColor"/>
          <path opacity="0.4" d="M12.75 18.3281V16.0781H11.25V18.3281H9C8.58579 18.3281 8.25 18.6639 8.25 19.0781C8.25 19.4923 8.58579 19.8281 9 19.8281H15C15.4142 19.8281 15.75 19.4923 15.75 19.0781C15.75 18.6639 15.4142 18.3281 15 18.3281H12.75Z" fill="currentColor"/>
        </svg>
      ) : (
        // Dark mode icon (monitor for dark)
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M4.25 4.17188C3.00736 4.17188 2 5.17923 2 6.42187V13.8281C2 15.0708 3.00736 16.0781 4.25 16.0781H11.25H12.75H19.75C20.9926 16.0781 22 15.0708 22 13.8281V6.42188C22 5.17923 20.9926 4.17188 19.75 4.17188H4.25ZM3.5 6.42187C3.5 6.00766 3.83579 5.67188 4.25 5.67188H19.75C20.1642 5.67188 20.5 6.00766 20.5 6.42188V13.8281C20.5 14.2423 20.1642 14.5781 19.75 14.5781H4.25C3.83579 14.5781 3.5 14.2423 3.5 13.8281V6.42187Z" fill="currentColor"/>
          <path opacity="0.4" d="M12.75 18.3281V16.0781H11.25V18.3281H9C8.58579 18.3281 8.25 18.6639 8.25 19.0781C8.25 19.4923 8.58579 19.8281 9 19.8281H15C15.4142 19.8281 15.75 19.4923 15.75 19.0781C15.75 18.6639 15.4142 18.3281 15 18.3281H12.75Z" fill="currentColor"/>
        </svg>
      )}
    </button>
  );
}