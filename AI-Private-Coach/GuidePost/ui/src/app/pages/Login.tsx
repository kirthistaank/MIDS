import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Sparkles, ArrowRight } from 'lucide-react';
import { getUserByEmail, resetUser, upsertUser } from '../lib/api';

export default function Login() {
  const [isNewUser, setIsNewUser] = useState<boolean | null>(null);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const clearLocalGuidepostState = () => {
    localStorage.removeItem('userId');
    localStorage.removeItem('userEmail');
    localStorage.removeItem('userName');
    localStorage.removeItem('userOccupation');
    localStorage.removeItem('userSeniorityLevel');
    localStorage.removeItem('rankedSkills');
    localStorage.removeItem('otherFocus');
    localStorage.removeItem('voiceRecorded');
    localStorage.removeItem('guidepost.chatState.v3');
    localStorage.removeItem('guidepost.chatState.v2');
    localStorage.removeItem('guidepost.chatState.v1');
  };

  const handleNewUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (email && name) {
      setError(null);
      try {
        // Create the user row immediately so "returning user" works even mid-onboarding.
        const u = await upsertUser({ email, name });
        localStorage.setItem('userId', u.id);
        localStorage.setItem('userEmail', u.email);
        localStorage.setItem('userName', u.name || name);
      } catch {
        // Best-effort: keep onboarding usable even if DB is unavailable.
        localStorage.setItem('userEmail', email);
        localStorage.setItem('userName', name);
      }
      navigate('/onboarding/occupation');
    }
  };

  const handleExistingUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (email) {
      setError(null);
      try {
        const u = await getUserByEmail({ email });
        localStorage.setItem('userId', u.id);
        localStorage.setItem('userEmail', u.email);
        if (u.name) localStorage.setItem('userName', u.name);
        if (u.occupation) localStorage.setItem('userOccupation', u.occupation);
        if (u.seniorityLevel) localStorage.setItem('userSeniorityLevel', u.seniorityLevel);
        if (u.rankedSkills) localStorage.setItem('rankedSkills', JSON.stringify(u.rankedSkills));
        if (typeof u.otherFocus === 'string') localStorage.setItem('otherFocus', u.otherFocus);
        if (typeof u.voiceRecorded === 'boolean') localStorage.setItem('voiceRecorded', u.voiceRecorded ? 'true' : 'false');
        navigate('/dashboard');
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Sign-in failed.';
        setError(msg);
      }
    }
  };

  const handleReset = async () => {
    setError(null);
    const emailToReset = (email || localStorage.getItem('userEmail') || '').trim();
    try {
      if (emailToReset) await resetUser({ email: emailToReset });
    } catch {
      // ignore
    } finally {
      clearLocalGuidepostState();
      setIsNewUser(null);
      setEmail('');
      setName('');
    }
  };

  if (isNewUser === null) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
        <div className="p-8">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              Guidepost
            </h1>
          </div>
        </div>

        <div className="flex items-center justify-center px-6 py-16">
          <div className="w-full max-w-md">
            <div className="text-center mb-12">
              <h2 className="text-5xl font-bold mb-4 bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                Welcome
              </h2>
              <p className="text-lg text-slate-600">Your AI-powered professional development coach</p>
            </div>

            <div className="space-y-4">
              <button
                onClick={() => setIsNewUser(true)}
                className="group w-full p-8 bg-white rounded-2xl shadow-lg shadow-indigo-100 hover:shadow-xl hover:shadow-indigo-200 transition-all duration-300 text-left border-2 border-transparent hover:border-indigo-200 relative overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-600 to-purple-600 opacity-0 group-hover:opacity-5 transition-opacity duration-300" />
                <div className="relative">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xl font-semibold text-slate-900">I&apos;m new here</div>
                    <ArrowRight className="w-5 h-5 text-indigo-600 transform group-hover:translate-x-1 transition-transform" />
                  </div>
                  <div className="text-slate-600">Create your profile and set up your coaching preferences</div>
                </div>
              </button>

              <button
                onClick={() => setIsNewUser(false)}
                className="group w-full p-8 bg-white rounded-2xl shadow-lg shadow-indigo-100 hover:shadow-xl hover:shadow-indigo-200 transition-all duration-300 text-left border-2 border-transparent hover:border-indigo-200 relative overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-600 to-purple-600 opacity-0 group-hover:opacity-5 transition-opacity duration-300" />
                <div className="relative">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xl font-semibold text-slate-900">I have an account</div>
                    <ArrowRight className="w-5 h-5 text-indigo-600 transform group-hover:translate-x-1 transition-transform" />
                  </div>
                  <div className="text-slate-600">Sign in to continue your development journey</div>
                </div>
              </button>

              <Button type="button" variant="ghost" className="w-full h-12" onClick={handleReset}>
                Reset app (clear saved chat + user)
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (isNewUser) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
        <div className="p-8">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              Guidepost
            </h1>
          </div>
        </div>

        <div className="flex items-center justify-center px-6 py-12">
          <div className="w-full max-w-md">
            <div className="bg-white rounded-3xl shadow-2xl shadow-indigo-100 p-10">
              <div className="text-center mb-8">
                <h2 className="text-4xl font-bold mb-3 text-slate-900">Let&apos;s get started</h2>
                <p className="text-slate-600">Tell us a bit about yourself to personalize your experience</p>
              </div>

              <form onSubmit={handleNewUserSubmit} className="space-y-6">
                <div className="space-y-5">
                  <div>
                    <Label htmlFor="name" className="text-slate-700">
                      Full name
                    </Label>
                    <Input
                      id="name"
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      placeholder="John Doe"
                      className="mt-2 h-12 rounded-xl border-slate-200 focus:border-indigo-500 focus:ring-indigo-500"
                    />
                  </div>

                  <div>
                    <Label htmlFor="email" className="text-slate-700">
                      Email address
                    </Label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      placeholder="you@example.com"
                      className="mt-2 h-12 rounded-xl border-slate-200 focus:border-indigo-500 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full h-12 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200"
                >
                  Continue
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>

                <Button type="button" variant="ghost" className="w-full h-12" onClick={() => setIsNewUser(null)}>
                  Back
                </Button>
              </form>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      <div className="p-8">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            Guidepost
          </h1>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-3xl shadow-2xl shadow-indigo-100 p-10">
            <div className="text-center mb-8">
              <h2 className="text-4xl font-bold mb-3 text-slate-900">Welcome back</h2>
              <p className="text-slate-600">Sign in to continue improving your professional skills</p>
            </div>

            {error && <div className="mb-4 text-sm text-red-600">{error}</div>}
            <form onSubmit={handleExistingUserSubmit} className="space-y-6">
              <div>
                <Label htmlFor="email" className="text-slate-700">
                  Email address
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@example.com"
                  className="mt-2 h-12 rounded-xl border-slate-200 focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>

              <Button
                type="submit"
                className="w-full h-12 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200"
              >
                Sign In
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>

              <Button type="button" variant="ghost" className="w-full h-12" onClick={() => setIsNewUser(null)}>
                Back
              </Button>

              <Button type="button" variant="ghost" className="w-full h-12" onClick={handleReset}>
                Reset app (clear saved chat + user)
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}