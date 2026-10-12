import emberSrc from '../../assets/ember.png';
import './EmberBackground.css';

const EMBERS = 
[
  { top: '4%',  left: '8%',  width: '9vw' },
  { top: '14%', left: '80%', width: '7vw' },
  { top: '38%', left: '2%',  width: '5.5vw' },
  { top: '52%', left: '68%', width: '10vw' },
  { top: '74%', left: '20%', width: '6.5vw' },
  { top: '86%', left: '52%', width: '5vw' },
  { top: '8%',  left: '44%', width: '4vw' },
  { top: '64%', left: '92%', width: '6vw' },
  { top: '96%', left: '8%',  width: '4.5vw' },
  { top: '28%', left: '60%', width: '3.5vw' },
];

export default function EmberBackground() 
{
  return (
    <div className="bg-embers" aria-hidden="true">
      {EMBERS.map((style, i) => (
        <img key={i} src={emberSrc} alt="" style={style} />
      ))}
    </div>
  );
}