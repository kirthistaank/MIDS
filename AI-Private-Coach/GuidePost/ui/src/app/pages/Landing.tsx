import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import {
  ArrowRight,
  BarChart3,
  Brain,
  Lightbulb,
  MessageSquare,
  Mic,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  Users,
} from 'lucide-react';

const features = [
  {
    icon: Mic,
    title: 'Record Real Conversations',
    description: 'Upload audio from meetings, calls, or any interaction you want to improve.',
  },
  {
    icon: Brain,
    title: 'AI-Powered Analysis',
    description: 'Our system analyzes language patterns, conversation flow, and vocal delivery.',
  },
  {
    icon: Target,
    title: 'Personalized Feedback',
    description: 'Receive actionable insights aligned with your specific communication goals.',
  },
  {
    icon: TrendingUp,
    title: 'Track Progress',
    description: 'Monitor patterns over time and see measurable improvement in your skills.',
  },
  {
    icon: Shield,
    title: 'Private & Secure',
    description: 'Your conversations stay confidential. Non-judgmental, evidence-based coaching.',
  },
  {
    icon: Lightbulb,
    title: 'Practical Strategies',
    description: 'Get concrete suggestions you can apply in your next conversation.',
  },
];

const focusAreas = [
  {
    icon: MessageSquare,
    title: 'Effective Communication',
    description: 'Clarity, structure, and message delivery',
  },
  {
    icon: Users,
    title: 'Emotional Intelligence',
    description: 'Understanding and managing interpersonal dynamics',
  },
  {
    icon: Target,
    title: 'Conflict Resolution',
    description: 'Navigating difficult conversations with confidence',
  },
  {
    icon: BarChart3,
    title: 'Influence & Negotiation',
    description: 'Persuasion and strategic communication',
  },
  {
    icon: TrendingUp,
    title: 'Feedback Delivery',
    description: 'Giving and receiving feedback effectively',
  },
];

const howItWorks = [
  {
    step: '01',
    title: 'Define Your Goals',
    description: 'Tell us what communication skills you want to develop during a quick onboarding process.',
  },
  {
    step: '02',
    title: 'Upload & Analyze',
    description: 'Record or upload conversations with context about what you would like feedback on.',
  },
  {
    step: '03',
    title: 'Receive Coaching',
    description: 'Get personalized insights on patterns, dynamics, and strategies for improvement.',
  },
];

export default function Landing() {
  const navigate = useNavigate();

  const handleSeeHowItWorks = () => {
    const el = document.getElementById('how-it-works');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-indigo-50/30">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-lg border-b border-purple-100">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                Guidepost
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <Button
                className="rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200"
                onClick={() => navigate('/login')}
              >
                Sign In
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-50 border border-indigo-200 rounded-full mb-6">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <span className="text-sm font-medium text-indigo-700">AI-Powered Communication Coaching</span>
              </div>
              <h2 className="text-5xl lg:text-6xl font-bold text-slate-900 mb-6 leading-tight">
                Bridge the gap between{' '}
                <span className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                  intent and impact
                </span>
              </h2>
              <p className="text-xl text-slate-600 mb-8 leading-relaxed">
                Understand how you communicate in real conversations. Get personalized, evidence-based coaching to
                develop stronger interpersonal skills.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <Button
                  size="lg"
                  className="rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200 h-14 px-8"
                  onClick={() => navigate('/login')}
                >
                  Start Your Journey
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  className="rounded-xl border-slate-300 hover:border-indigo-300 hover:bg-indigo-50 h-14 px-8"
                  onClick={handleSeeHowItWorks}
                >
                  See How It Works
                </Button>
              </div>
            </div>
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-400 to-purple-600 rounded-3xl blur-3xl opacity-20" />
              <div className="relative rounded-3xl overflow-hidden shadow-2xl shadow-indigo-200/50">
                <ImageWithFallback
                  src="https://images.unsplash.com/photo-1758518727600-2c5f48419eac?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxwcm9mZXNzaW9uYWwlMjBidXNpbmVzcyUyMGNvbnZlcnNhdGlvbiUyMG1lZXRpbmd8ZW58MXx8fHwxNzc0MzE0Nzc3fDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                  alt="Professional business conversation"
                  className="w-full h-full object-cover"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 px-6 bg-white scroll-mt-28">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h3 className="text-4xl font-bold text-slate-900 mb-4">How Guidepost Works</h3>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">
              Simple, private, and personalized coaching in three easy steps
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {howItWorks.map((item, index) => (
              <div key={index} className="relative">
                {index < howItWorks.length - 1 && (
                  <div className="hidden md:block absolute top-16 left-full w-full h-0.5 bg-gradient-to-r from-indigo-200 to-transparent -translate-x-1/2" />
                )}
                <div className="relative bg-gradient-to-br from-slate-50 to-indigo-50/50 rounded-2xl p-8 border border-slate-200 hover:shadow-xl hover:shadow-indigo-100 transition-all duration-300">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600 text-white text-2xl font-bold mb-6 shadow-lg shadow-indigo-200">
                    {item.step}
                  </div>
                  <h4 className="text-2xl font-bold text-slate-900 mb-3">{item.title}</h4>
                  <p className="text-slate-600 leading-relaxed">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h3 className="text-4xl font-bold text-slate-900 mb-4">Your Personal Communication Coach</h3>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">Powered by AI, designed for real-world improvement</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <div
                  key={index}
                  className="group bg-white rounded-2xl p-8 border-2 border-slate-100 hover:border-indigo-200 hover:shadow-xl hover:shadow-indigo-100 transition-all duration-300"
                >
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform duration-300">
                    <Icon className="w-7 h-7 text-indigo-700" />
                  </div>
                  <h4 className="text-xl font-bold text-slate-900 mb-3">{feature.title}</h4>
                  <p className="text-slate-600 leading-relaxed">{feature.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Focus Areas */}
      <section className="py-20 px-6 bg-gradient-to-br from-slate-900 to-slate-800 text-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h3 className="text-4xl font-bold mb-4">Areas We Help You Master</h3>
            <p className="text-xl text-slate-300 max-w-2xl mx-auto">
              Personalized coaching across the skills that matter most
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-6">
            {focusAreas.map((area, index) => {
              const Icon = area.icon;
              return (
                <div
                  key={index}
                  className="bg-white/5 backdrop-blur-sm rounded-2xl p-6 border border-white/10 hover:bg-white/10 hover:border-purple-400/30 transition-all duration-300"
                >
                  <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center mb-4">
                    <Icon className="w-6 h-6 text-purple-400" />
                  </div>
                  <h4 className="font-bold mb-2">{area.title}</h4>
                  <p className="text-sm text-slate-400">{area.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Analysis Dimensions */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="relative order-2 lg:order-1">
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-400 to-purple-600 rounded-3xl blur-3xl opacity-20" />
              <div className="relative rounded-3xl overflow-hidden shadow-2xl shadow-indigo-200/50">
                <ImageWithFallback
                  src="https://images.unsplash.com/photo-1611532736579-6b16e2b50449?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHx3b21hbiUyMHByb2Zlc3Npb25hbCUyMGhlYWRwaG9uZXMlMjBhdWRpb3xlbnwxfHx8fDE3NzQzMTQ3Nzh8MA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                  alt="Professional with headphones"
                  className="w-full h-full object-cover"
                />
              </div>
            </div>
            <div className="order-1 lg:order-2">
              <h3 className="text-4xl font-bold text-slate-900 mb-6">Three-Dimensional Analysis</h3>
              <p className="text-lg text-slate-600 mb-8">
                We analyze every conversation across multiple layers to give you the complete picture.
              </p>
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center">
                    <MessageSquare className="w-6 h-6 text-indigo-700" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 mb-2">What You Said</h4>
                    <p className="text-slate-600">Language patterns, word choice, and message structure</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center">
                    <Users className="w-6 h-6 text-indigo-700" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 mb-2">Conversation Flow</h4>
                    <p className="text-slate-600">Turn-taking, interruptions, and participation balance</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center">
                    <BarChart3 className="w-6 h-6 text-indigo-700" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 mb-2">How You Said It</h4>
                    <p className="text-slate-600">Vocal delivery, pace, tone, and emphasis</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 bg-slate-900 text-white">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold">Guidepost</span>
            </div>
            <div className="flex gap-8 text-sm text-slate-400">
              <a href="#" className="hover:text-white transition-colors">
                Privacy
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Terms
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Contact
              </a>
            </div>
            <div className="text-sm text-slate-400">© 2026 Guidepost. All rights reserved.</div>
          </div>
        </div>
      </footer>
    </div>
  );
}

