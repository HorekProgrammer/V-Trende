
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import './CoverViewer.css';

const TILT = 14;

export default function CoverViewer({ src, title, onClose })
{
  const imgRef = useRef(null);
  const tapAnimationRef = useRef(null);

  useEffect(() => 
  {
    const onKey = (e) => 
    {
      if (e.key === 'Escape') 
      {
        onClose();
      }
    };

    const prevOverflow = document.body.style.overflow;

    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';

    return () => 
    {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
      tapAnimationRef.current?.cancel();
    };
  }, [onClose]);

  const onMove = (e) => 
  {
    const img = imgRef.current;

    if (!img || window.matchMedia('(prefers-reduced-motion: reduce)').matches) 
    {
      return;
    }

    const r = img.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;

    img.style.transform =
      `perspective(900px) rotateY(${x * TILT}deg) rotateX(${-y * TILT}deg) scale(1.02)`;
  };

  const onLeave = () => 
  {
    if (imgRef.current) 
    {
      imgRef.current.style.transform = '';
    }
  };

  const onImageClick = (e) =>
  {
    e.stopPropagation();

    const img = imgRef.current;

    if (!img || window.matchMedia('(prefers-reduced-motion: reduce)').matches)
    {
      return;
    }

    tapAnimationRef.current?.cancel();

    tapAnimationRef.current = img.animate(
      [
        { transform: 'scale(1)' },
        { transform: 'scale(1.07)', offset: 0.15 },
        { transform: 'scale(1.07)', offset: 0.8 },
        { transform: 'scale(1)' }
      ],
      {
        duration: 1000,
        easing: 'ease-in-out',
        iterations: 1
      }
    );
  };

  return createPortal(
    <div
      className="cv-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
    >
      <img
        ref={imgRef}
        className="cv-img"
        src={src}
        alt={title}
        draggable={false}
        referrerPolicy="no-referrer"
        onClick={onImageClick}
      />
      <button type="button" className="cv-close" onClick={onClose}>Закрыть</button>
    </div>,
    document.body
  );
}
