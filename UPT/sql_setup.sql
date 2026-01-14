-- ============================================================================
-- SCRIPTS SQL PARA SISTEMA DE TRANSCRIPCIÓN Y ANÁLISIS CON TOKENS
-- Base de datos: Merida_VW
-- ============================================================================

USE Merida_VW;
GO

-- ============================================================================
-- 1. TABLA PRINCIPAL (si no existe)
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[AudioQueue]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[AudioQueue](
        [TransactionId] [int] IDENTITY(1,1) NOT NULL,
        [RutaAudio] [nvarchar](500) NOT NULL,
        [Estado] [nvarchar](50) NOT NULL DEFAULT 'Pendiente',
        [RutaTranscripcion] [nvarchar](500) NULL,
        [NombreTranscripcion] [nvarchar](255) NULL,
        [RutaAnalisis] [nvarchar](500) NULL,
        [NombreAnalisis] [nvarchar](255) NULL,
        [TokensTranscripcionIn] [int] NULL DEFAULT 0,
        [TokensTranscripcionOut] [int] NULL DEFAULT 0,
        [TokensAnalisisIn] [int] NULL DEFAULT 0,
        [TokensAnalisisOut] [int] NULL DEFAULT 0,
        [ReintentoCount] [int] NOT NULL DEFAULT 0,
        [FechaCreacion] [datetime] NOT NULL DEFAULT GETDATE(),
        [FechaActualizacion] [datetime] NULL,
        CONSTRAINT [PK_AudioQueue] PRIMARY KEY CLUSTERED ([TransactionId] ASC)
    ) ON [PRIMARY]
    
    PRINT '✅ Tabla AudioQueue creada exitosamente'
END
ELSE
BEGIN
    PRINT 'ℹ️ La tabla AudioQueue ya existe'
    
    -- Agregar columnas si no existen
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('AudioQueue') AND name = 'TokensTranscripcionIn')
        ALTER TABLE AudioQueue ADD TokensTranscripcionIn INT NULL DEFAULT 0;
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('AudioQueue') AND name = 'TokensTranscripcionOut')
        ALTER TABLE AudioQueue ADD TokensTranscripcionOut INT NULL DEFAULT 0;
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('AudioQueue') AND name = 'TokensAnalisisIn')
        ALTER TABLE AudioQueue ADD TokensAnalisisIn INT NULL DEFAULT 0;
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('AudioQueue') AND name = 'TokensAnalisisOut')
        ALTER TABLE AudioQueue ADD TokensAnalisisOut INT NULL DEFAULT 0;
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('AudioQueue') AND name = 'ReintentoCount')
        ALTER TABLE AudioQueue ADD ReintentoCount INT NOT NULL DEFAULT 0;
    
    PRINT '✅ Columnas actualizadas'
END
GO

-- ============================================================================
-- 2. ÍNDICES PARA MEJORAR PERFORMANCE
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AudioQueue_Estado' AND object_id = OBJECT_ID('AudioQueue'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_AudioQueue_Estado]
    ON [dbo].[AudioQueue] ([Estado])
    INCLUDE ([TransactionId], [RutaAudio], [RutaTranscripcion], [ReintentoCount])
    
    PRINT '✅ Índice IX_AudioQueue_Estado creado'
END
GO

-- ============================================================================
-- 3. SP: GetPendingTranscriptions
-- Obtiene los últimos 2 registros pendientes de transcribir
-- ============================================================================

IF EXISTS (SELECT * FROM sys.objects WHERE type = 'P' AND name = 'GetPendingTranscriptions')
    DROP PROCEDURE GetPendingTranscriptions;
GO

CREATE PROCEDURE GetPendingTranscriptions
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT TOP 2
        TransactionId,
        RutaAudio,
        ReintentoCount
    FROM AudioQueue
    WHERE Estado = 'Pendiente'
      AND RutaTranscripcion IS NULL
    ORDER BY TransactionId ASC;
END
GO

PRINT '✅ SP GetPendingTranscriptions creado'
GO

-- ============================================================================
-- 4. SP: GetPendingAnalysis
-- Obtiene los últimos 2 registros pendientes de analizar
-- ============================================================================

IF EXISTS (SELECT * FROM sys.objects WHERE type = 'P' AND name = 'GetPendingAnalysis')
    DROP PROCEDURE GetPendingAnalysis;
GO

CREATE PROCEDURE GetPendingAnalysis
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT TOP 2
        TransactionId,
        RutaAudio,
        RutaTranscripcion,
        ReintentoCount
    FROM AudioQueue
    WHERE Estado = 'Pendiente'
      AND RutaTranscripcion IS NOT NULL
      AND RutaAnalisis IS NULL
    ORDER BY TransactionId ASC;
END
GO

PRINT '✅ SP GetPendingAnalysis creado'
GO

-- ============================================================================
-- 5. SP: SetTranscription
-- Actualiza la transcripción con tokens
-- ============================================================================

IF EXISTS (SELECT * FROM sys.objects WHERE type = 'P' AND name = 'SetTranscription')
    DROP PROCEDURE SetTranscription;
GO

CREATE PROCEDURE SetTranscription
    @TransactionId INT,
    @RutaTranscripcion NVARCHAR(500),
    @NombreTranscripcion NVARCHAR(255),
    @TokensIn INT,
    @TokensOut INT
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE AudioQueue
    SET 
        RutaTranscripcion = @RutaTranscripcion,
        NombreTranscripcion = @NombreTranscripcion,
        TokensTranscripcionIn = @TokensIn,
        TokensTranscripcionOut = @TokensOut,
        FechaActualizacion = GETDATE(),
        ReintentoCount = 0  -- Resetear reintentos al completar
    WHERE TransactionId = @TransactionId;
    
    IF @@ROWCOUNT > 0
        PRINT '✅ Transcripción actualizada para TransactionId: ' + CAST(@TransactionId AS VARCHAR);
END
GO

PRINT '✅ SP SetTranscription creado'
GO

-- ============================================================================
-- 6. SP: SetAnalysis
-- Actualiza el análisis con tokens
-- ============================================================================

IF EXISTS (SELECT * FROM sys.objects WHERE type = 'P' AND name = 'SetAnalysis')
    DROP PROCEDURE SetAnalysis;
GO

CREATE PROCEDURE SetAnalysis
    @TransactionId INT,
    @RutaAnalisis NVARCHAR(500),
    @NombreAnalisis NVARCHAR(255),
    @TokensIn INT,
    @TokensOut INT
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE AudioQueue
    SET 
        RutaAnalisis = @RutaAnalisis,
        NombreAnalisis = @NombreAnalisis,
        TokensAnalisisIn = @TokensIn,
        TokensAnalisisOut = @TokensOut,
        Estado = 'Completado',
        FechaActualizacion = GETDATE(),
        ReintentoCount = 0  -- Resetear reintentos al completar
    WHERE TransactionId = @TransactionId;
    
    IF @@ROWCOUNT > 0
        PRINT '✅ Análisis actualizado para TransactionId: ' + CAST(@TransactionId AS VARCHAR);
END
GO

PRINT '✅ SP SetAnalysis creado'
GO

-- ============================================================================
-- 7. SP: IncrementRetryCount
-- Incrementa el contador de reintentos
-- ============================================================================

IF EXISTS (SELECT * FROM sys.objects WHERE type = 'P' AND name = 'IncrementRetryCount')
    DROP PROCEDURE IncrementRetryCount;
GO

CREATE PROCEDURE IncrementRetryCount
    @TransactionId INT,
    @NewRetryCount INT
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE AudioQueue
    SET 
        ReintentoCount = @NewRetryCount,
        FechaActualizacion = GETDATE()
    WHERE TransactionId = @TransactionId;
    
    IF @@ROWCOUNT > 0
        PRINT '⚠️ Reintentos incrementados para TransactionId: ' + CAST(@TransactionId AS VARCHAR) + ' -> ' + CAST(@NewRetryCount AS VARCHAR);
END
GO

PRINT '✅ SP IncrementRetryCount creado'
GO

-- ============================================================================
-- 8. SP: UpdateTransactionStatus
-- Actualiza el estado de una transacción (incluyendo error)
-- ============================================================================

IF EXISTS (SELECT * FROM sys.objects WHERE type = 'P' AND name = 'UpdateTransactionStatus')
    DROP PROCEDURE UpdateTransactionStatus;
GO

CREATE PROCEDURE UpdateTransactionStatus
    @TransactionId INT,
    @NewStatus NVARCHAR(50),
    @RetryCount INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE AudioQueue
    SET 
        Estado = @NewStatus,
        ReintentoCount = ISNULL(@RetryCount, ReintentoCount),
        FechaActualizacion = GETDATE()
    WHERE TransactionId = @TransactionId;
    
    IF @@ROWCOUNT > 0
        PRINT '✅ Estado actualizado para TransactionId: ' + CAST(@TransactionId AS VARCHAR) + ' -> ' + @NewStatus;
END
GO

PRINT '✅ SP UpdateTransactionStatus creado'
GO

-- ============================================================================
-- 9. SP: GetMonthlyTokenUsage
-- Obtiene la suma de tokens consumidos en un mes específico
-- ============================================================================

IF EXISTS (SELECT * FROM sys.objects WHERE type = 'P' AND name = 'GetMonthlyTokenUsage')
    DROP PROCEDURE GetMonthlyTokenUsage;
GO

CREATE PROCEDURE GetMonthlyTokenUsage
    @Year INT,
    @Month INT
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        SUM(ISNULL(TokensTranscripcionIn, 0) + ISNULL(TokensAnalisisIn, 0)) AS TotalTokensIn,
        SUM(ISNULL(TokensTranscripcionOut, 0) + ISNULL(TokensAnalisisOut, 0)) AS TotalTokensOut
    FROM AudioQueue
    WHERE YEAR(FechaActualizacion) = @Year
      AND MONTH(FechaActualizacion) = @Month
      AND Estado = 'Completado';
END
GO

PRINT '✅ SP GetMonthlyTokenUsage creado'
GO

-- ============================================================================
-- 10. VISTA: ResumenTokensPorMes
-- Vista para análisis rápido de consumo mensual
-- ============================================================================

IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_ResumenTokensPorMes')
    DROP VIEW vw_ResumenTokensPorMes;
GO

CREATE VIEW vw_ResumenTokensPorMes
AS
SELECT 
    YEAR(FechaActualizacion) AS Año,
    MONTH(FechaActualizacion) AS Mes,
    DATENAME(MONTH, FechaActualizacion) AS NombreMes,
    COUNT(*) AS TotalProcesados,
    SUM(ISNULL(TokensTranscripcionIn, 0)) AS TokensTranscripcionIn,
    SUM(ISNULL(TokensTranscripcionOut, 0)) AS TokensTranscripcionOut,
    SUM(ISNULL(TokensAnalisisIn, 0)) AS TokensAnalisisIn,
    SUM(ISNULL(TokensAnalisisOut, 0)) AS TokensAnalisisOut,
    SUM(ISNULL(TokensTranscripcionIn, 0) + ISNULL(TokensAnalisisIn, 0)) AS TotalTokensIn,
    SUM(ISNULL(TokensTranscripcionOut, 0) + ISNULL(TokensAnalisisOut, 0)) AS TotalTokensOut,
    SUM(ISNULL(TokensTranscripcionIn, 0) + ISNULL(TokensAnalisisIn, 0) + 
        ISNULL(TokensTranscripcionOut, 0) + ISNULL(TokensAnalisisOut, 0)) AS TotalTokens
FROM AudioQueue
WHERE Estado = 'Completado'
  AND FechaActualizacion IS NOT NULL
GROUP BY 
    YEAR(FechaActualizacion),
    MONTH(FechaActualizacion),
    DATENAME(MONTH, FechaActualizacion);
GO

PRINT '✅ Vista vw_ResumenTokensPorMes creada'
GO

-- ============================================================================
-- 11. CONSULTAS DE PRUEBA
-- ============================================================================

PRINT ''
PRINT '============================================================================'
PRINT 'CONSULTAS DE VERIFICACIÓN'
PRINT '============================================================================'

-- Ver estructura de la tabla
PRINT ''
PRINT '📋 Columnas de AudioQueue:'
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'AudioQueue'
ORDER BY ORDINAL_POSITION;

-- Ver stored procedures creados
PRINT ''
PRINT '📋 Stored Procedures creados:'
SELECT 
    name AS ProcedureName,
    create_date AS FechaCreacion,
    modify_date AS UltimaModificacion
FROM sys.procedures
WHERE name IN (
    'GetPendingTranscriptions',
    'GetPendingAnalysis',
    'SetTranscription',
    'SetAnalysis',
    'IncrementRetryCount',
    'UpdateTransactionStatus',
    'GetMonthlyTokenUsage'
)
ORDER BY name;

PRINT ''
PRINT '============================================================================'
PRINT '✅ INSTALACIÓN COMPLETADA'
PRINT '============================================================================'
PRINT ''
PRINT 'Ejemplo de uso:'
PRINT '-- Insertar registro de prueba:'
PRINT 'INSERT INTO AudioQueue (RutaAudio, Estado) VALUES (''D:\Audio\test.wav'', ''Pendiente'');'
PRINT ''
PRINT '-- Ver pendientes de transcribir:'
PRINT 'EXEC GetPendingTranscriptions;'
PRINT ''
PRINT '-- Ver pendientes de analizar:'
PRINT 'EXEC GetPendingAnalysis;'
PRINT ''
PRINT '-- Ver uso mensual de tokens:'
PRINT 'EXEC GetMonthlyTokenUsage 2025, 1;'
PRINT ''
PRINT '-- Ver resumen por mes:'
PRINT 'SELECT * FROM vw_ResumenTokensPorMes ORDER BY Año DESC, Mes DESC;'
PRINT '============================================================================'
GO